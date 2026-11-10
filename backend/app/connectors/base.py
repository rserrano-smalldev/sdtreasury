"""ERP-agnostic connector contract.

Business logic never talks to an ERP directly: it consumes these canonical records,
produced by one ``ErpConnector`` implementation per ERP (and version).
"""

from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel


class ErpCompany(BaseModel):
    erp_id: int
    name: str
    vat: str | None = None
    currency: str


class ErpBankAccount(BaseModel):
    erp_id: int
    company_erp_id: int
    name: str
    iban: str | None = None
    bank_name: str | None = None
    currency: str
    sync_source: str | None = None
    active: bool = True
    write_date: datetime | None = None


class ErpBankBalance(BaseModel):
    bank_account_erp_id: int
    balance: Decimal
    currency: str


class ErpBankTransaction(BaseModel):
    erp_id: int
    bank_account_erp_id: int
    company_erp_id: int
    date: date
    amount: Decimal
    currency: str
    label: str | None = None
    partner_erp_id: int | None = None
    partner_name: str | None = None
    counterpart_account: str | None = None
    transaction_type: str | None = None
    is_reconciled: bool = False
    write_date: datetime | None = None


class ErpOpenItem(BaseModel):
    erp_id: int
    company_erp_id: int
    kind: Literal["receivable", "payable"]
    number: str | None = None
    reference: str | None = None
    partner_erp_id: int | None = None
    partner_name: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str
    amount_total: Decimal  # signed, company currency
    amount_residual: Decimal  # signed, company currency
    payment_state: str | None = None
    is_open: bool
    write_date: datetime | None = None


class Batch[T](BaseModel):
    """A page of records plus the cursor to resume from after processing it."""

    records: list[T]
    cursor: str | None


class ErpConnector(Protocol):
    def test_connection(self) -> dict: ...

    def companies(self) -> list[ErpCompany]: ...

    def bank_accounts(self) -> list[ErpBankAccount]: ...

    def bank_balances(self, bank_account_erp_ids: list[int]) -> list[ErpBankBalance]: ...

    def bank_transactions(self, since: str | None) -> Iterator[Batch[ErpBankTransaction]]: ...

    def open_items(self, since: str | None) -> Iterator[Batch[ErpOpenItem]]: ...

    def open_items_by_ids(self, erp_ids: list[int]) -> list[ErpOpenItem]: ...
