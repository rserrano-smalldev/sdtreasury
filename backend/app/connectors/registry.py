"""Build the right connector for an ``ErpConnection``."""

from app.connectors.base import ErpConnector
from app.connectors.demo import DemoConnector
from app.connectors.odoo.client import OdooClient
from app.connectors.odoo.connector import OdooConnector
from app.core.config import get_settings
from app.core.secrets import resolve_secret
from app.models import ErpConnection


class UnsupportedErp(Exception):
    pass


def build_connector(conn: ErpConnection) -> ErpConnector:
    settings = get_settings()
    if conn.kind == "demo":
        return DemoConnector()
    if conn.kind == "odoo" and conn.version.startswith("18."):
        client = OdooClient(
            conn.base_url,
            conn.database,
            conn.username,
            resolve_secret(conn.secret_ref),
            timeout=settings.odoo_timeout_seconds,
        )
        return OdooConnector(client, page_size=settings.odoo_page_size)
    raise UnsupportedErp(f"No connector for {conn.kind} {conn.version}")
