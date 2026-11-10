import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import Module


class Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CompanyOut(Orm):
    id: uuid.UUID
    name: str
    vat: str | None
    currency: str
    modules: list[Module] = []


class EntitlementIn(BaseModel):
    company_id: uuid.UUID
    module: Module
    valid_from: date
    valid_to: date | None = None
    is_trial: bool = False


class EntitlementOut(Orm):
    id: uuid.UUID
    company_id: uuid.UUID
    module: Module
    valid_from: date
    valid_to: date | None
    is_trial: bool


class BankAccountOut(Orm):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    iban: str | None
    bank_name: str | None
    currency: str
    sync_source: str | None
    balance: Decimal
    balance_at: datetime | None


class BankTransactionOut(Orm):
    id: uuid.UUID
    bank_account_id: uuid.UUID
    date: date
    amount: Decimal
    currency: str
    label: str | None
    partner_name: str | None
    is_reconciled: bool


class OpenItemOut(Orm):
    id: uuid.UUID
    company_id: uuid.UUID
    kind: str
    number: str | None
    partner_name: str | None
    invoice_date: date | None
    due_date: date | None
    currency: str
    amount_total: Decimal
    amount_residual: Decimal
    payment_state: str | None


class CurrencyTotal(BaseModel):
    currency: str
    balance: Decimal
    receivables: Decimal
    payables: Decimal


class PositionOut(BaseModel):
    as_of: datetime | None
    totals: list[CurrencyTotal]
    accounts: list[BankAccountOut]


class SyncOut(BaseModel):
    companies: int
    bank_accounts: int
    bank_transactions: int
    open_items: int
    open_items_refreshed: int
