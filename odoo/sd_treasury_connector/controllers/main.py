"""Login into SD Treasury from Odoo.

Builds a short-lived, single-use token signed with the secret shared with the platform
(HMAC-SHA256) and redirects the browser to the platform. The token travels in the URL
fragment (``#token=``) so it never reaches server logs. Format must match
``backend/app/core/sso.py``.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import quote

from odoo import http
from odoo.http import request

from ..models.res_config_settings import PARAM_SECRET, PARAM_TENANT, PARAM_URL

TOKEN_LIFETIME_SECONDS = 60


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def sign(payload: dict, secret: str) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    mac = hmac.new(secret.encode(), f"v1.{body}".encode(), hashlib.sha256).digest()
    return f"v1.{body}.{_b64(mac)}"


class SdTreasuryController(http.Controller):
    @http.route("/sd_treasury/launch", type="http", auth="user", methods=["GET"])
    def launch(self, **kwargs):
        user = request.env.user
        if not user.has_group("sd_treasury_connector.group_sd_treasury_user"):
            return request.not_found()

        params = request.env["ir.config_parameter"].sudo()
        url, tenant, secret = (params.get_param(p) for p in (PARAM_URL, PARAM_TENANT, PARAM_SECRET))
        if not (url and tenant and secret):
            return request.make_response(
                "SD Treasury no está configurado. Revisa Contabilidad → Ajustes → SD Treasury.",
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=503,
            )

        roles = (
            ["admin"]
            if user.has_group("sd_treasury_connector.group_sd_treasury_manager")
            else ["viewer"]
        )
        now = int(time.time())
        payload = {
            "tenant": tenant,
            "db": request.db,
            "login": user.login,
            "name": user.name,
            "email": user.email or "",
            "roles": roles,
            "company_ids": user.company_ids.ids,
            "iat": now,
            "exp": now + TOKEN_LIFETIME_SECONDS,
            "jti": secrets.token_hex(16),
        }
        target = f"{url.rstrip('/')}/sso/odoo#token={quote(sign(payload, secret))}"
        return request.redirect(target, local=False)
