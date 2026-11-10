"""Resolve secret references stored in the database.

References look like ``env:VAR_NAME`` (dev) or ``aws:<secret ARN or name>`` (AWS Secrets
Manager). Secrets themselves are never stored in the platform database.
"""

import os


class SecretNotFound(Exception):
    pass


def resolve_secret(ref: str) -> str:
    scheme, _, value = ref.partition(":")
    if scheme == "env":
        secret = os.environ.get(value)
        if not secret:
            raise SecretNotFound(f"Environment variable {value!r} is not set")
        return secret
    if scheme == "aws":
        import boto3  # optional dependency: pip install .[aws]

        client = boto3.client("secretsmanager")
        return client.get_secret_value(SecretId=value)["SecretString"]
    raise SecretNotFound(f"Unsupported secret reference scheme: {scheme!r}")
