"""Login from Odoo: verification of the launch token signed by ``sd_treasury_connector``.

Format: ``v1.<base64url(json payload)>.<base64url(HMAC-SHA256)>``; the MAC covers
``v1.<payload>`` and uses the per-connection shared secret (``ErpConnection.sso_secret_ref``).

Payload: ``tenant`` (slug), ``login``, ``name``, ``email``, ``roles`` (platform roles),
``company_ids`` (Odoo company ids), ``iat``, ``exp`` (unix seconds), ``jti`` (single use).
"""

import base64
import hashlib
import hmac
import json
import time

VERSION = "v1"
MAX_LIFETIME_SECONDS = 300
CLOCK_SKEW_SECONDS = 30


class SsoError(Exception):
    pass


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def sign(payload: dict, secret: str) -> str:
    """Reference implementation of the Odoo side (used by tests)."""
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    mac = hmac.new(secret.encode(), f"{VERSION}.{body}".encode(), hashlib.sha256).digest()
    return f"{VERSION}.{body}.{_b64encode(mac)}"


def peek(token: str) -> dict:
    """Decode the payload WITHOUT verifying it, only to find which tenant signed it."""
    try:
        version, body, _ = token.split(".")
        if version != VERSION:
            raise SsoError("Unsupported token version")
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise SsoError("Malformed token") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("tenant"), str):
        raise SsoError("Malformed token")
    return payload


def verify(token: str, secret: str, now: float | None = None) -> dict:
    payload = peek(token)
    version, body, mac = token.split(".")
    expected = hmac.new(secret.encode(), f"{version}.{body}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64decode(mac)):
        raise SsoError("Bad signature")
    now = time.time() if now is None else now
    try:
        iat, exp = float(payload["iat"]), float(payload["exp"])
        if not payload["login"] or not payload["jti"]:
            raise KeyError
    except (KeyError, TypeError, ValueError) as exc:
        raise SsoError("Missing claims") from exc
    if exp - iat > MAX_LIFETIME_SECONDS:
        raise SsoError("Token lifetime too long")
    if iat > now + CLOCK_SKEW_SECONDS or exp < now - CLOCK_SKEW_SECONDS:
        raise SsoError("Token expired")
    return payload
