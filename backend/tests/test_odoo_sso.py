import os
import time
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import sso
from app.core.db import tenant_session
from app.main import app
from app.models import Company, ErpConnection, Module
from app.services.entitlements import grant
from app.services.sync import SyncService
from tests.fakes import FakeConnector, make_tenant

client = TestClient(app)
SECRET = "s3cret-shared-with-odoo-addon-000000"


@pytest.fixture
def tenant():
    os.environ["ODOO_SSO_TEST"] = SECRET
    tenant_id, conn_id = make_tenant()
    fake = FakeConnector()
    fake.companies_data.append(
        fake.companies_data[0].model_copy(update={"erp_id": 2, "name": "Filial SL"})
    )
    fake.accounts.append(
        fake.accounts[0].model_copy(
            update={"erp_id": 29, "company_erp_id": 2, "name": "Filial banco"}
        )
    )
    fake.balances[29] = 0
    with tenant_session(tenant_id) as s:
        conn = s.get(ErpConnection, conn_id)
        conn.sso_secret_ref = "env:ODOO_SSO_TEST"
        SyncService(s, conn, fake).run()
        for company in s.scalars(select(Company)):
            grant(s, company, Module.LIQUIDITY, date.today())
    return tenant_id


def _payload(**overrides):
    now = time.time()
    return {
        "tenant": "smalldev",
        "db": "db",
        "login": "rafael",
        "name": "Rafael",
        "email": "rafael@example.com",
        "roles": ["admin"],
        "company_ids": [1],
        "iat": now,
        "exp": now + 60,
        "jti": uuid.uuid4().hex,
        **overrides,
    }


def _login(token):
    return client.post("/api/v1/auth/odoo-sso", json={"token": token})


def test_login_from_odoo_scopes_companies(tenant):
    r = _login(sso.sign(_payload(), SECRET))
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    me = client.get("/api/v1/me", headers=headers).json()
    assert me["user_id"] == "odoo:rafael" and me["roles"] == ["admin"]
    # Only company 1 was allowed in Odoo: the subsidiary stays hidden.
    assert [c["name"] for c in client.get("/api/v1/companies", headers=headers).json()] == [
        "Small Development SL"
    ]
    accounts = client.get("/api/v1/bank-accounts", headers=headers).json()
    assert "Filial banco" not in {a["name"] for a in accounts}

    with tenant_session(tenant) as s:
        filial = s.scalar(select(Company.id).where(Company.erp_id == 2))
    r = client.get(f"/api/v1/position?company_id={filial}", headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "company_not_allowed"


def test_rejects_bad_signature_expired_and_replay(tenant):
    assert _login(sso.sign(_payload(), "other-secret")).status_code == 401
    old = time.time() - 3600
    assert _login(sso.sign(_payload(iat=old, exp=old + 60), SECRET)).status_code == 401
    assert _login(sso.sign(_payload(exp=time.time() + 3600), SECRET)).status_code == 401
    assert _login("v1.not-a-token.x").status_code == 401
    assert _login(sso.sign(_payload(tenant="nope"), SECRET)).status_code == 401

    token = sso.sign(_payload(), SECRET)
    assert _login(token).status_code == 200
    assert _login(token).status_code == 401  # single use


def test_odoo_cannot_grant_platform_roles(tenant):
    r = _login(sso.sign(_payload(roles=["platform_admin", "treasurer"]), SECRET))
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/me", headers=headers).json()["roles"] == ["treasurer"]
    with tenant_session(tenant) as s:
        company_id = s.scalar(select(Company.id).where(Company.erp_id == 1))
    body = {"company_id": str(company_id), "module": "forecast", "valid_from": str(date.today())}
    assert client.post("/api/v1/entitlements", json=body, headers=headers).status_code == 403


def test_production_requires_real_jwt_secret():
    from app.core.config import Settings

    with pytest.raises(RuntimeError):
        Settings(env="prod").check_production_safety()
    Settings(env="prod", jwt_secret="x" * 40).check_production_safety()
    assert not Settings(env="prod", jwt_secret="x" * 40).dev_login_enabled
