"""Test setup: a real PostgreSQL database with the migrations applied.

The app connects as the non-owner role ``sdt_app`` so Row-Level Security is enforced
exactly as in production. Override with SDT_TEST_DATABASE_URL / SDT_TEST_OWNER_URL.
"""

import os

OWNER_URL = os.environ.get(
    "SDT_TEST_OWNER_URL",
    "postgresql+psycopg://sdtreasury:sdtreasury@localhost:5432/sdtreasury_test",
)
APP_URL = os.environ.get(
    "SDT_TEST_DATABASE_URL",
    "postgresql+psycopg://sdt_app:sdt_app@localhost:5432/sdtreasury_test",
)
os.environ["SDT_ENV"] = "test"
os.environ["SDT_AUTH_MODE"] = "dev"
os.environ["SDT_DATABASE_URL"] = APP_URL
os.environ["SDT_MIGRATION_DATABASE_URL"] = OWNER_URL

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.models import TENANT_TABLES  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(migrated_db):
    yield
    engine = create_engine(OWNER_URL)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(['tenant', *TENANT_TABLES])} CASCADE"))
    engine.dispose()
