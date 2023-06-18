# PromptLink

[![PyPI version](https://badge.fury.io/py/promptlink.svg)](https://badge.fury.io/py/promptlink)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Simplify user authentication and secure access from anywhere with temporary links.

PromptLink is a Python package that allows you to streamline user authentication and enable secure access to your application from anywhere. It provides a seamless way to generate temporary links for user authentication, without relying on specific web frameworks. A Google Cloud Function is set up to ensure a secure temporary link for authentication.

## Key Features

- **Easy and secure**: Generate secure temporary links to enable easy secure access from anywhere.
- **Versatile Integration**: Works across various application types, not limited to web applications.

## Installation

You can install PromptLink using pip:
```shell
pip install promptlink
```
Alternatively, if you are using Poetry (recommended), you can install it as follows:
```shell
poetry add promptlink
```

## Usage

Here's a basic example of using PromptLink:

```python
from promptlink import Authenticator


with Authenticator(send_link_callback=lambda l: print(f"URL: {l}")) as authenticator:
    # The code in this block is executed after the link has been accessed 
    # in order to avoid authentication timeouts
    print("Setting up authentication...")
    authenticator.authenticate(lambda s: s == "12345678")
    # Below statements will be reached after '12345678' was input on the webpage prompt
    print("Finished")
```

## GCP permission requirements
The following permissions are needed for this library:
- Permissions to create Storage buckets and objects
- Permissions to set up a Pub/Sub topic and subscriptions
- Permissions to deploy a Cloud Function  

The library will attempt to use the default service account.
Any resources created will be named 'promptlink-' followed by a random UUID, so that collision with existing resources is extremely unlikely.

## License
This project is licensed under the MIT License. See the LICENSE file for details.
