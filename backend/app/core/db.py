"""Database engine and tenant-scoped sessions.

Every tenant-owned table has Row-Level Security enabled (see migrations). A session
must declare its tenant with ``SET LOCAL app.tenant_id`` before touching tenant data;
``tenant_session`` does that for the lifetime of one transaction.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def set_tenant(session: Session, tenant_id: UUID) -> None:
    session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})


@contextmanager
def tenant_session(tenant_id: UUID) -> Iterator[Session]:
    """Session bound to one tenant; commits on success, rolls back on error."""
    with SessionLocal() as session, session.begin():
        set_tenant(session, tenant_id)
        yield session


@contextmanager
def platform_session() -> Iterator[Session]:
    """Session without tenant scope: only for platform-level tables (tenants, plans)."""
    with SessionLocal() as session, session.begin():
        yield session
