from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError

from app.core.db import SessionLocal, tenant_session
from app.models import BankAccount, BankTransaction, Company, ErpConnection, OpenItem, SyncState
from app.services.sync import STREAM_BANK_TRANSACTIONS, SyncService
from tests.fakes import FakeConnector, item, make_tenant


def _sync(tenant_id, conn_id, connector):
    with tenant_session(tenant_id) as s:
        conn = s.get(ErpConnection, conn_id)
        return SyncService(s, conn, connector).run()


def test_full_then_incremental_sync_is_idempotent():
    tenant_id, conn_id = make_tenant()
    fake = FakeConnector()
    report = _sync(tenant_id, conn_id, fake)
    assert (report.companies, report.bank_accounts, report.bank_transactions) == (1, 2, 5)

    report = _sync(tenant_id, conn_id, fake)
    # Second run resumes from the cursor (">=" re-reads only the last record).
    assert fake.since_calls[-2] == "2026-11-05 09:00:00"
    assert report.bank_transactions == 1

    with tenant_session(tenant_id) as s:
        assert s.scalar(select(func.count()).select_from(BankTransaction)) == 5
        santander = s.scalar(select(BankAccount).where(BankAccount.erp_id == 27))
        assert santander.balance == Decimal("1500.50")
        state = s.scalar(select(SyncState).where(SyncState.stream == STREAM_BANK_TRANSACTIONS))
        assert state.cursor == "2026-11-05 09:00:00"


def test_refresh_closes_paid_and_deleted_items():
    tenant_id, conn_id = make_tenant()
    fake = FakeConnector()
    _sync(tenant_id, conn_id, fake)

    # Item 1 gets paid without its write_date moving; item 2 is deleted in the ERP.
    fake.items[1] = item(1, residual="0.00", is_open=False)
    del fake.items[2]
    _sync(tenant_id, conn_id, fake)

    with tenant_session(tenant_id) as s:
        states = dict(s.execute(select(OpenItem.erp_id, OpenItem.is_open)).all())
    assert states == {1: False, 2: False}


def test_rls_isolates_tenants():
    a, conn_a = make_tenant("alpha")
    b, _ = make_tenant("beta")
    _sync(a, conn_a, FakeConnector())

    with tenant_session(b) as s:
        assert s.scalar(select(func.count()).select_from(Company)) == 0
        assert s.scalar(select(func.count()).select_from(BankTransaction)) == 0
    with tenant_session(a) as s:
        assert s.scalar(select(func.count()).select_from(Company)) == 1

    # Writing a row for another tenant is rejected by the policy's WITH CHECK.
    with pytest.raises(ProgrammingError), tenant_session(b) as s:
        s.add(Company(tenant_id=a, erp_connection_id=conn_a, erp_id=99, name="X", currency="EUR"))
        s.flush()

    # Without a tenant set, nothing is visible.
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(Company)) == 0
