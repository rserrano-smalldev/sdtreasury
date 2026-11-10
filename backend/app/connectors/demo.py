"""Synthetic ERP for local development and sales demos (``kind="demo"``)."""

import random
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.connectors.base import (
    Batch,
    ErpBankAccount,
    ErpBankBalance,
    ErpBankTransaction,
    ErpCompany,
    ErpOpenItem,
)

TODAY = date.today()
CUSTOMERS = ["Construcciones Norte SL", "Retail Levante SA", "Clínica Dental Sur", "Hotel Mar SL"]
VENDORS = ["AWS EMEA SARL", "Telefónica de España", "Asesoría Fiscal SL", "Oficinas Centro SL"]


class DemoConnector:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.write = datetime(TODAY.year, TODAY.month, TODAY.day, 8, 0, 0)

    def test_connection(self) -> dict:
        return {"server_version": "demo"}

    def companies(self) -> list[ErpCompany]:
        return [ErpCompany(erp_id=1, name="Demo Tecnología SL", vat="ESB00000001", currency="EUR")]

    def bank_accounts(self) -> list[ErpBankAccount]:
        return [
            ErpBankAccount(
                erp_id=1,
                company_erp_id=1,
                name="Banco A",
                currency="EUR",
                iban="ES9100490000000000000001",
                bank_name="Banco A",
                sync_source="online_sync",
            ),
            ErpBankAccount(
                erp_id=2,
                company_erp_id=1,
                name="Banco B",
                currency="EUR",
                iban="ES9121000000000000000002",
                bank_name="Banco B",
                sync_source="online_sync",
            ),
        ]

    def bank_balances(self, ids: list[int]) -> list[ErpBankBalance]:
        values = {1: Decimal("84210.37"), 2: Decimal("12950.10")}
        return [
            ErpBankBalance(bank_account_erp_id=i, balance=values[i], currency="EUR")
            for i in ids
            if i in values
        ]

    def bank_transactions(self, since: str | None) -> Iterator[Batch[ErpBankTransaction]]:
        if since:
            return
        records = []
        for i in range(120):
            inflow = self.rng.random() < 0.4
            party = self.rng.choice(CUSTOMERS if inflow else VENDORS)
            amount = Decimal(self.rng.randint(150, 9000)) * (1 if inflow else -1)
            records.append(
                ErpBankTransaction(
                    erp_id=i + 1,
                    bank_account_erp_id=self.rng.choice([1, 1, 2]),
                    company_erp_id=1,
                    date=TODAY - timedelta(days=i // 2),
                    amount=amount,
                    currency="EUR",
                    label=("Transferencia de " if inflow else "Pago a ") + party,
                    partner_name=party,
                    is_reconciled=self.rng.random() < 0.8,
                    write_date=self.write,
                )
            )
        yield Batch(records=records, cursor=self.write.strftime("%Y-%m-%d %H:%M:%S"))

    def _items(self) -> list[ErpOpenItem]:
        items = []
        for i in range(30):
            receivable = i % 2 == 0
            amount = Decimal(self.rng.randint(500, 15000)) * (1 if receivable else -1)
            items.append(
                ErpOpenItem(
                    erp_id=i + 1,
                    company_erp_id=1,
                    kind="receivable" if receivable else "payable",
                    number=f"{'FV' if receivable else 'FP'}/2026/{i + 1:04d}",
                    partner_name=self.rng.choice(CUSTOMERS if receivable else VENDORS),
                    invoice_date=TODAY - timedelta(days=30),
                    due_date=TODAY + timedelta(days=i * 3 - 20),
                    currency="EUR",
                    amount_total=amount,
                    amount_residual=amount,
                    payment_state="not_paid",
                    is_open=True,
                    write_date=self.write,
                )
            )
        return items

    def open_items(self, since: str | None) -> Iterator[Batch[ErpOpenItem]]:
        if since:
            return
        yield Batch(records=self._items(), cursor=self.write.strftime("%Y-%m-%d %H:%M:%S"))

    def open_items_by_ids(self, erp_ids: list[int]) -> list[ErpOpenItem]:
        wanted = set(erp_ids)
        return [i for i in self._items() if i.erp_id in wanted]
