"""Read-only mirror of ERP data, in the canonical (ERP-agnostic) shape."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantOwned, Timestamps, UUIDPk

Money = Numeric(18, 2)


class ErpMirrored(TenantOwned):
    erp_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_connection.id", ondelete="CASCADE")
    )
    erp_id: Mapped[int] = mapped_column(Integer)
    erp_write_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BankAccount(UUIDPk, Timestamps, ErpMirrored, Base):
    """A bank account (``account.journal`` of type bank in Odoo)."""

    __tablename__ = "bank_account"
    __table_args__ = (UniqueConstraint("tenant_id", "erp_connection_id", "erp_id"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    iban: Mapped[str | None] = mapped_column(String(64))
    bank_name: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3))
    sync_source: Mapped[str | None] = mapped_column(String(32))
    balance: Mapped[Decimal] = mapped_column(Money, default=0)
    balance_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BankTransaction(UUIDPk, Timestamps, ErpMirrored, Base):
    """A bank movement (``account.bank.statement.line`` in Odoo)."""

    __tablename__ = "bank_transaction"
    __table_args__ = (
        UniqueConstraint("tenant_id", "erp_connection_id", "erp_id"),
        Index("ix_bank_transaction_account_date", "bank_account_id", "date"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE"), index=True
    )
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_account.id", ondelete="CASCADE")
    )
    date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    label: Mapped[str | None] = mapped_column(Text)
    partner_erp_id: Mapped[int | None] = mapped_column(Integer)
    partner_name: Mapped[str | None] = mapped_column(String(300))
    counterpart_account: Mapped[str | None] = mapped_column(String(64))
    transaction_type: Mapped[str | None] = mapped_column(String(64))
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)


class OpenItem(UUIDPk, Timestamps, ErpMirrored, Base):
    """A customer or vendor invoice/refund (``account.move`` in Odoo)."""

    __tablename__ = "open_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "erp_connection_id", "erp_id"),
        Index("ix_open_item_company_due", "company_id", "is_open", "due_date"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("company.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(16))  # receivable | payable
    number: Mapped[str | None] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(300))
    partner_erp_id: Mapped[int | None] = mapped_column(Integer)
    partner_name: Mapped[str | None] = mapped_column(String(300))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    # Signed in company currency: receivables positive, payables negative.
    amount_total: Mapped[Decimal] = mapped_column(Money)
    amount_residual: Mapped[Decimal] = mapped_column(Money)
    payment_state: Mapped[str | None] = mapped_column(String(32))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)


class SyncState(UUIDPk, Timestamps, TenantOwned, Base):
    """Incremental sync cursor per ERP connection and data stream."""

    __tablename__ = "sync_state"
    __table_args__ = (UniqueConstraint("tenant_id", "erp_connection_id", "stream"),)

    erp_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_connection.id", ondelete="CASCADE")
    )
    stream: Mapped[str] = mapped_column(String(64))
    cursor: Mapped[str | None] = mapped_column(String(64))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
