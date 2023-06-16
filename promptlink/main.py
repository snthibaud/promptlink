import json
import os
from typing import Optional

import functions_framework
from flask import Request
from google.cloud.exceptions import NotFound
from google.cloud.pubsub_v1 import PublisherClient
from google.auth import default
from google.cloud import storage

from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("static"),
    autoescape=select_autoescape()
)

TOPIC_ID_PREFIX = "promptlink-"
SUBSCRIPTION_ID_PREFIX = "promptlink-subscription-"
_, PROJECT_ID = default()
AUTHENTICATION_ID_HEADER = "Authentication-ID"
ACTION = "X-Action"
STATUS_PREPARING = "preparing"
STATUS_AUTHENTICATING = "authenticating"
AUTHENTICATION_RESULT_BLOB = "authentication_result"


def get_authentication_id(request: Request) -> str:
    return request.headers.get(AUTHENTICATION_ID_HEADER)


def get_bucket_name(authentication_id: str) -> str:
    return f"promptlink-{authentication_id}"


def get_topic_path(authentication_id: str) -> str:
    return PublisherClient.topic_path(PROJECT_ID, TOPIC_ID_PREFIX + authentication_id)


def publish_message(authentication_id: str, action: str, data: Optional[str] = None):
    publisher = PublisherClient()
    payload = action + (f"-{data}" if data else "")
    publisher.publish(get_topic_path(authentication_id), payload.encode())


def start(request: Request):
    publish_message(get_authentication_id(request), "start")
    return STATUS_PREPARING


def authenticate(request: Request):
    input_data = json.loads(request.data.decode()).get("input")
    if input_data:
        publish_message(get_authentication_id(request), "input", input_data)
        status = "authenticating"
    else:
        try:
            storage.Client().get_bucket(get_bucket_name(get_authentication_id(request)))
            status = "ready"
        except NotFound:
            status = STATUS_PREPARING
    return status


def poll_authentication_status(request: Request):
    authentication_id = get_authentication_id(request)
    try:
        blob = storage.Client().get_bucket(get_bucket_name(authentication_id)).get_blob(
            AUTHENTICATION_RESULT_BLOB)
        if blob:
            status = blob.download_as_string()
            publish_message(authentication_id, "statusread")
        else:
            status = STATUS_AUTHENTICATING
    except NotFound:
        status = STATUS_AUTHENTICATING
    return status


@functions_framework.http
def entrypoint(request: Request):
    return {"start": start, "authenticate": authenticate, "poll_authentication_status": poll_authentication_status}.get(
        request.headers.get(ACTION), lambda _: env.get_template("index.html").render(
            authentication_id=os.environ['K_SERVICE'].removeprefix("promptlink-")))(request)
