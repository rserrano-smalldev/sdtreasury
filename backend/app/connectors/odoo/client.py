"""Minimal Odoo external API client (JSON-RPC, Odoo 18).

Odoo 19 adds the JSON-2 API and deprecates JSON-RPC/XML-RPC; a ``Json2Transport`` will be
added behind the same ``execute_kw`` signature when we support 19.
"""

from itertools import count
from typing import Any

import httpx


class OdooError(Exception):
    def __init__(self, message: str, data: dict | None = None):
        super().__init__(message)
        self.data = data or {}


class OdooClient:
    def __init__(
        self,
        base_url: str,
        database: str,
        username: str,
        api_key: str,
        *,
        timeout: float = 60.0,
        http: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.username = username
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=timeout)
        self._ids = count(1)
        self._uid: int | None = None
        self.context: dict[str, Any] = {}

    def _call(self, service: str, method: str, *args: Any) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": list(args)},
            "id": next(self._ids),
        }
        response = self._http.post(f"{self.base_url}/jsonrpc", json=payload)
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            err = body["error"]
            message = err.get("data", {}).get("message") or err.get("message", "Odoo error")
            raise OdooError(message, err.get("data"))
        return body.get("result")

    @property
    def uid(self) -> int:
        if self._uid is None:
            uid = self._call(
                "common", "authenticate", self.database, self.username, self._api_key, {}
            )
            if not uid:
                raise OdooError("Authentication failed: check database, login and API key")
            self._uid = uid
        return self._uid

    def version(self) -> dict:
        return self._call("common", "version")

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict | None = None) -> Any:
        kwargs = dict(kwargs or {})
        kwargs["context"] = {**self.context, **kwargs.get("context", {})}
        return self._call(
            "object",
            "execute_kw",
            self.database,
            self.uid,
            self._api_key,
            model,
            method,
            args,
            kwargs,
        )

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        *,
        order: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        kwargs: dict[str, Any] = {"fields": fields, "offset": offset}
        if order:
            kwargs["order"] = order
        if limit:
            kwargs["limit"] = limit
        return self.execute_kw(model, "search_read", [domain], kwargs)
