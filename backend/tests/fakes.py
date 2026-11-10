"""In-memory ERP connector producing canonical records."""

from datetime import date, datetime
from decimal import Decimal

from app.connectors.base import (
    Batch,
    ErpBankAccount,
    ErpBankBalance,
    ErpBankTransaction,
    ErpCompany,
    ErpOpenItem,
)
from app.core.db import platform_session, tenant_session
from app.models import ErpConnection, Tenant


def make_tenant(slug: str = "smalldev"):
    with platform_session() as s:
        tenant = Tenant(name=slug.title(), slug=slug)
        s.add(tenant)
        s.flush()
        tenant_id = tenant.id
    with tenant_session(tenant_id) as s:
        conn = ErpConnection(
            tenant_id=tenant_id,
            base_url="http://odoo.internal",
            database="db",
            username="api@test",
            secret_ref="env:ODOO_TEST_KEY",
        )
        s.add(conn)
        s.flush()
        return tenant_id, conn.id


def item(
    erp_id,
    kind="receivable",
    residual="100.00",
    is_open=True,
    due=date(2026, 12, 1),
    company=1,
    write=datetime(2026, 11, 1, 10, 0, 0),
):
    amount = Decimal(residual)
    return ErpOpenItem(
        erp_id=erp_id,
        company_erp_id=company,
        kind=kind,
        number=f"INV/{erp_id}",
        partner_erp_id=7,
        partner_name="Cliente SA",
        invoice_date=date(2026, 11, 1),
        due_date=due,
        currency="EUR",
        amount_total=amount,
        amount_residual=amount,
        payment_state="not_paid" if is_open else "paid",
        is_open=is_open,
        write_date=write,
    )


class FakeConnector:
    def __init__(self):
        self.companies_data = [ErpCompany(erp_id=1, name="Small Development SL", currency="EUR")]
        self.accounts = [
            ErpBankAccount(
                erp_id=27,
                company_erp_id=1,
                name="Santander",
                currency="EUR",
                iban="ES0000000000000000000027",
                sync_source="online_sync",
            ),
            ErpBankAccount(
                erp_id=28, company_erp_id=1, name="Caixa", currency="EUR", sync_source="online_sync"
            ),
        ]
        self.balances = {27: Decimal("1500.50"), 28: Decimal("-200.00")}
        self.transactions = [
            ErpBankTransaction(
                erp_id=100 + i,
                bank_account_erp_id=27,
                company_erp_id=1,
                date=date(2026, 11, i + 1),
                amount=Decimal("10.00"),
                currency="EUR",
                label=f"Mov {i}",
                write_date=datetime(2026, 11, i + 1, 9, 0, 0),
            )
            for i in range(5)
        ]
        self.items = {i.erp_id: i for i in [item(1), item(2, kind="payable", residual="-40.00")]}
        self.since_calls: list[str | None] = []

    def test_connection(self):
        return {"ok": True}

    def companies(self):
        return self.companies_data

    def bank_accounts(self):
        return self.accounts

    def bank_balances(self, ids):
        return [
            ErpBankBalance(bank_account_erp_id=i, balance=self.balances[i], currency="EUR")
            for i in ids
        ]

    def _batches(self, records, since, size=2):
        self.since_calls.append(since)
        records = [r for r in records if since is None or r.write_date.isoformat(" ") >= since]
        records.sort(key=lambda r: (r.write_date, r.erp_id))
        for start in range(0, len(records), size):
            chunk = records[start : start + size]
            yield Batch(records=chunk, cursor=chunk[-1].write_date.isoformat(" "))

    def bank_transactions(self, since):
        return self._batches(self.transactions, since)

    def open_items(self, since):
        return self._batches(list(self.items.values()), since)

    def open_items_by_ids(self, ids):
        return [self.items[i] for i in ids if i in self.items]
