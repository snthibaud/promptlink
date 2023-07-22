from dataclasses import dataclass
from pathlib import Path
from queue import SimpleQueue
from subprocess import run
from threading import Event
from typing import Callable, Optional
from uuid import UUID, uuid4

from google.api_core.exceptions import NotFound
from google.cloud.exceptions import Conflict
from google.cloud.pubsub_v1 import SubscriberClient, PublisherClient
from google.cloud.pubsub_v1.subscriber.message import Message
from yaml import safe_load
from google.cloud import storage

from promptlink.main import PROJECT_ID, SUBSCRIPTION_ID_PREFIX, get_authentication_id, publish_message, TOPIC_ID_PREFIX, \
    get_topic_path, get_bucket_name, AUTHENTICATION_RESULT_BLOB


@dataclass
class Authenticator:
    send_link_callback: Callable[[str], None]
    gcp_region: str = "us-west1"
    _link: Optional[str] = None
    _function_name: Optional[str] = None
    _authentication_id: UUID = uuid4()
    _website_accessed: Event = Event()
    _status_relayed: Event = Event()
    _input_queue = SimpleQueue()
    _publisher: PublisherClient = PublisherClient()
    _subscriber: SubscriberClient = SubscriberClient()

    def _deploy_cloud_function(self) -> str:
        self._function_name = f"promptlink-{self._authentication_id}"
        output = run(
            f"gcloud functions deploy {self._function_name} --gen2 "
            f"--region={self.gcp_region} --runtime=python39 "
            f"--source=\"{Path(__file__).resolve().parent}\" --entry-point=entrypoint --trigger-http "
            f"--allow-unauthenticated", capture_output=True, text=True, shell=True)
        try:
            return safe_load(output.stdout)["serviceConfig"]["uri"]
        except TypeError:
            print(output.stderr)
            raise

    def _remove_cloud_function(self):
        print(run(f"gcloud functions delete {self._function_name} --quiet",
                  capture_output=True, text=True, shell=True).stdout)

    def _handle_message(self, message: Message):
        message.ack()
        payload = message.data.decode()
        if payload == "start":
            self._website_accessed.set()
        elif payload == "statusread":
            self._status_relayed.set()
        else:
            action, data = payload.split("-")
            assert action == "input"
            self._input_queue.put(data)

    @property
    def subscription_path(self):
        return self._subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID_PREFIX + str(self._authentication_id))

    @property
    def bucket(self):
        return storage.Client().get_bucket(get_bucket_name(str(self._authentication_id)))

    def __enter__(self):
        topic_path = get_topic_path(str(self._authentication_id))
        self._publisher.create_topic(request={"name": topic_path})
        self._link = self._deploy_cloud_function()
        self._subscriber = SubscriberClient()
        self._subscriber.create_subscription(request={"name": self.subscription_path, "topic": topic_path})
        self._subscriber.subscribe(self.subscription_path, callback=self._handle_message)
        self.send_link_callback(self._link)
        self._website_accessed.wait()
        return self

    def _get_input(self) -> str:
        try:
            storage.Client().create_bucket(get_bucket_name(str(self._authentication_id)), location=self.gcp_region)
        except Conflict:
            pass
        return self._input_queue.get()

    def authenticate(self, f: Callable[[str], bool]):
        success = False
        while not success:
            self._status_relayed.clear()
            try:
                self.bucket.blob(AUTHENTICATION_RESULT_BLOB).delete()
            except NotFound:
                pass
            success = f(self._get_input())
            self._relay_authentication_result(success)
            self._status_relayed.wait()

    def _relay_authentication_result(self, result: bool):
        with self.bucket.blob(AUTHENTICATION_RESULT_BLOB).open("w") as f:
            f.write("success" if result else "failure")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.bucket.delete(force=True)
        except NotFound:
            pass
        self._remove_cloud_function()
        self._subscriber.delete_subscription(request={"subscription": self.subscription_path})
        self._publisher.delete_topic(request={"topic": get_topic_path(str(self._authentication_id))})
