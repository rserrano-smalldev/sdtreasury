"""Alembic environment.

Migrations run as the schema owner (``SDT_MIGRATION_DATABASE_URL``); the application
connects as a non-owner role without BYPASSRLS (``SDT_DATABASE_URL``).
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
MIGRATION_LOCK_KEY = 74_201_811  # arbitrary, constant


def _url() -> str:
    return os.environ.get("SDT_MIGRATION_DATABASE_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # NullPool: the advisory lock is session-level, so the connection must really close.
    engine = create_engine(_url(), poolclass=NullPool)
    with engine.connect() as connection:
        # Serialise concurrent runs (several containers starting at once).
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_KEY})
            connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
