"""Operator commands: python -m app.cli <command> --help"""

import argparse
import json
import logging
import time
from datetime import date

from sqlalchemy import select

from app.connectors.registry import build_connector
from app.core.config import get_settings
from app.core.db import platform_session, tenant_session
from app.models import Company, ErpConnection, Module, Tenant
from app.services.entitlements import grant
from app.services.sync import SyncService


def create_tenant(args):
    with platform_session() as s:
        tenant = Tenant(name=args.name, slug=args.slug)
        s.add(tenant)
        s.flush()
        tenant_id = tenant.id
    with tenant_session(tenant_id) as s:
        conn = ErpConnection(
            tenant_id=tenant_id,
            kind=args.kind,
            version=args.odoo_version,
            base_url=args.odoo_url,
            database=args.odoo_db,
            username=args.odoo_login,
            secret_ref=args.secret_ref,
        )
        s.add(conn)
        s.flush()
        print(json.dumps({"tenant_id": str(tenant_id), "erp_connection_id": str(conn.id)}))


def _tenant(slug: str) -> Tenant:
    with platform_session() as s:
        tenant = s.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        raise SystemExit(f"Unknown tenant {slug!r}")
    return tenant


def test_connection(args):
    tenant = _tenant(args.tenant)
    with tenant_session(tenant.id) as s:
        for conn in s.scalars(select(ErpConnection)):
            print(conn.base_url, json.dumps(build_connector(conn).test_connection()))


def sync(args):
    tenant = _tenant(args.tenant)
    with tenant_session(tenant.id) as s:
        for conn in s.scalars(select(ErpConnection).where(ErpConnection.active.is_(True))):
            report = SyncService(s, conn, build_connector(conn)).run()
            print(conn.base_url, json.dumps(vars(report)))


def sync_all() -> None:
    """Sync every active connection of every active tenant; one failure never stops the rest."""
    log = logging.getLogger("sdtreasury.scheduler")
    with platform_session() as s:
        tenants = s.scalars(select(Tenant).where(Tenant.active.is_(True))).all()
    for tenant in tenants:
        try:
            with tenant_session(tenant.id) as s:
                conns = s.scalars(select(ErpConnection).where(ErpConnection.active.is_(True)))
                for conn in conns:
                    report = SyncService(s, conn, build_connector(conn)).run()
                    log.info("synced %s %s: %s", tenant.slug, conn.base_url, vars(report))
        except Exception:
            log.exception("sync failed for tenant %s", tenant.slug)


def scheduler(args):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    interval = args.interval or get_settings().sync_interval_seconds
    while True:
        started = time.monotonic()
        sync_all()
        if args.once:
            return
        time.sleep(max(60, interval - (time.monotonic() - started)))


def set_sso_secret(args):
    tenant = _tenant(args.tenant)
    with tenant_session(tenant.id) as s:
        for conn in s.scalars(select(ErpConnection)):
            conn.sso_secret_ref = args.secret_ref
            print(f"{conn.base_url}: sso_secret_ref={args.secret_ref}")


def grant_module(args):
    tenant = _tenant(args.tenant)
    with tenant_session(tenant.id) as s:
        companies = s.scalars(select(Company)).all()
        if args.company:
            companies = [c for c in companies if c.name == args.company]
        for company in companies:
            for module in args.modules:
                grant(
                    s,
                    company,
                    Module(module),
                    date.fromisoformat(args.valid_from),
                    is_trial=args.trial,
                )
                print(f"{company.name}: {module}")


def main():
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("create-tenant", help="Create a tenant with its Odoo connection")
    p.add_argument("--name", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--kind", default="odoo", choices=["odoo", "demo"])
    p.add_argument("--odoo-url", default="")
    p.add_argument("--odoo-db", default="")
    p.add_argument("--odoo-login", default="")
    p.add_argument("--odoo-version", default="18.0")
    p.add_argument("--secret-ref", default="", help="env:VAR or aws:secret-arn")
    p.set_defaults(func=create_tenant)

    p = sub.add_parser("test-connection", help="Check access to the tenant's ERP")
    p.add_argument("--tenant", required=True)
    p.set_defaults(func=test_connection)

    p = sub.add_parser("sync", help="Run a sync for every active ERP connection of a tenant")
    p.add_argument("--tenant", required=True)
    p.set_defaults(func=sync)

    p = sub.add_parser("scheduler", help="Periodic sync of all tenants (MVP worker)")
    p.add_argument("--interval", type=int, help="Seconds between runs (default from settings)")
    p.add_argument("--once", action="store_true", help="Run a single pass and exit")
    p.set_defaults(func=scheduler)

    p = sub.add_parser("set-sso-secret", help="Secret shared with the Odoo addon for login")
    p.add_argument("--tenant", required=True)
    p.add_argument("--secret-ref", required=True, help="env:VAR or aws:secret-arn")
    p.set_defaults(func=set_sso_secret)

    p = sub.add_parser("grant", help="Activate modules for the tenant's companies")
    p.add_argument("--tenant", required=True)
    p.add_argument("--company", help="Company name (default: all)")
    p.add_argument("--modules", nargs="+", required=True, choices=[m.value for m in Module])
    p.add_argument("--valid-from", default=date.today().isoformat())
    p.add_argument("--trial", action="store_true")
    p.set_defaults(func=grant_module)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
