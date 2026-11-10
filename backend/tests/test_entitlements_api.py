from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import tenant_session
from app.main import app
from app.models import Company, ErpConnection, Module
from app.services.entitlements import (
    ModuleNotSubscribed,
    active_modules,
    grant,
    require_module,
)
from app.services.sync import SyncService
from tests.fakes import FakeConnector, make_tenant

client = TestClient(app)
TODAY = date.today()


@pytest.fixture
def synced():
    tenant_id, conn_id = make_tenant()
    with tenant_session(tenant_id) as s:
        SyncService(s, s.get(ErpConnection, conn_id), FakeConnector()).run()
        company_id = s.scalar(select(Company.id))
    return tenant_id, company_id


def _token(slug="smalldev", roles=("admin",)):
    r = client.post("/api/v1/auth/dev-token", json={"tenant_slug": slug, "roles": list(roles)})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_modules_require_liquidity_and_respect_dates(synced):
    tenant_id, company_id = synced
    with tenant_session(tenant_id) as s:
        company = s.get(Company, company_id)
        grant(s, company, Module.FORECAST, TODAY)
        assert active_modules(s).get(company_id, set()) == set()  # no base module yet
        grant(s, company, Module.LIQUIDITY, TODAY - timedelta(days=30), TODAY - timedelta(days=1))
        assert active_modules(s).get(company_id, set()) == set()  # expired
        grant(s, company, Module.LIQUIDITY, TODAY)
        assert active_modules(s)[company_id] == {Module.LIQUIDITY, Module.FORECAST}
        require_module(s, Module.FORECAST, company_id)
        with pytest.raises(ModuleNotSubscribed):
            require_module(s, Module.COLLECT, company_id)


def test_api_requires_token():
    assert client.get("/api/v1/companies").status_code == 401


def test_position_is_gated_by_liquidity_module(synced):
    tenant_id, company_id = synced
    headers = _token()

    r = client.get("/api/v1/position", headers=headers)
    assert r.status_code == 200
    assert r.json()["accounts"] == []  # nothing contracted yet
    r = client.get(f"/api/v1/position?company_id={company_id}", headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "module_not_subscribed"

    # Only platform admins can activate modules.
    body = {"company_id": str(company_id), "module": "liquidity", "valid_from": str(TODAY)}
    assert client.post("/api/v1/entitlements", json=body, headers=headers).status_code == 403
    r = client.post("/api/v1/entitlements", json=body, headers=_token(roles=["platform_admin"]))
    assert r.status_code == 201, r.text

    position = client.get("/api/v1/position", headers=headers).json()
    assert [a["name"] for a in position["accounts"]] == ["Caixa", "Santander"]
    eur = position["totals"][0]
    assert (eur["currency"], eur["balance"], eur["receivables"], eur["payables"]) == (
        "EUR",
        "1300.50",
        "100.00",
        "-40.00",
    )

    companies = client.get("/api/v1/companies", headers=headers).json()
    assert companies[0]["modules"] == ["liquidity"]
    txs = client.get("/api/v1/bank-transactions?limit=2", headers=headers).json()
    assert [t["label"] for t in txs] == ["Mov 4", "Mov 3"]
    items = client.get("/api/v1/open-items?kind=payable", headers=headers).json()
    assert [i["number"] for i in items] == ["INV/2"]
