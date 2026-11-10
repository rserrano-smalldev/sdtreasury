"""Pull data from an ERP connection into the canonical mirror tables."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.connectors.base import ErpConnector, ErpOpenItem
from app.models import BankAccount, BankTransaction, Company, ErpConnection, OpenItem, SyncState

log = logging.getLogger(__name__)

STREAM_BANK_TRANSACTIONS = "bank_transactions"
STREAM_OPEN_ITEMS = "open_items"
REFRESH_CHUNK = 200


@dataclass
class SyncReport:
    companies: int = 0
    bank_accounts: int = 0
    bank_transactions: int = 0
    open_items: int = 0
    open_items_refreshed: int = 0
    errors: list[str] = field(default_factory=list)


def _upsert(session: Session, model, rows: list[dict]) -> None:
    if not rows:
        return
    stmt = insert(model).values(rows)
    keys = ("tenant_id", "erp_connection_id", "erp_id")
    update_cols = {c: stmt.excluded[c] for c in rows[0] if c not in (*keys, "id")}
    update_cols["updated_at"] = datetime.now(UTC)
    session.execute(stmt.on_conflict_do_update(index_elements=list(keys), set_=update_cols))


def _id_map(session: Session, model, conn: ErpConnection) -> dict[int, uuid.UUID]:
    rows = session.execute(
        select(model.erp_id, model.id).where(model.erp_connection_id == conn.id)
    ).all()
    return dict(rows)


def _state(session: Session, conn: ErpConnection, stream: str) -> SyncState:
    state = session.scalar(
        select(SyncState).where(SyncState.erp_connection_id == conn.id, SyncState.stream == stream)
    )
    if state is None:
        state = SyncState(tenant_id=conn.tenant_id, erp_connection_id=conn.id, stream=stream)
        session.add(state)
        session.flush()
    return state


class SyncService:
    def __init__(self, session: Session, conn: ErpConnection, connector: ErpConnector):
        self.session = session
        self.conn = conn
        self.connector = connector
        self.base = {"tenant_id": conn.tenant_id, "erp_connection_id": conn.id}

    def run(self) -> SyncReport:
        report = SyncReport()
        report.companies = self.sync_companies()
        report.bank_accounts = self.sync_bank_accounts()
        report.bank_transactions = self.sync_bank_transactions()
        report.open_items = self.sync_open_items()
        report.open_items_refreshed = self.refresh_open_items()
        self.conn.last_sync_at = datetime.now(UTC)
        return report

    def sync_companies(self) -> int:
        companies = self.connector.companies()
        _upsert(
            self.session,
            Company,
            [
                {
                    **self.base,
                    "erp_id": c.erp_id,
                    "name": c.name,
                    "vat": c.vat,
                    "currency": c.currency,
                }
                for c in companies
            ],
        )
        return len(companies)

    def sync_bank_accounts(self) -> int:
        companies = _id_map(self.session, Company, self.conn)
        accounts = self.connector.bank_accounts()
        balances = {
            b.bank_account_erp_id: b
            for b in self.connector.bank_balances([a.erp_id for a in accounts if a.active])
        }
        now = datetime.now(UTC)
        rows = []
        for a in accounts:
            if a.company_erp_id not in companies:
                continue
            bal = balances.get(a.erp_id)
            rows.append(
                {
                    **self.base,
                    "erp_id": a.erp_id,
                    "company_id": companies[a.company_erp_id],
                    "name": a.name,
                    "iban": a.iban,
                    "bank_name": a.bank_name,
                    "currency": a.currency,
                    "sync_source": a.sync_source,
                    "active": a.active,
                    "erp_write_date": a.write_date,
                    "balance": bal.balance if bal else 0,
                    "balance_at": now if bal else None,
                }
            )
        _upsert(self.session, BankAccount, rows)
        return len(rows)

    def sync_bank_transactions(self) -> int:
        companies = _id_map(self.session, Company, self.conn)
        accounts = _id_map(self.session, BankAccount, self.conn)
        state = _state(self.session, self.conn, STREAM_BANK_TRANSACTIONS)
        total = 0
        for batch in self.connector.bank_transactions(state.cursor):
            rows = [
                {
                    **self.base,
                    "erp_id": t.erp_id,
                    "company_id": companies[t.company_erp_id],
                    "bank_account_id": accounts[t.bank_account_erp_id],
                    "date": t.date,
                    "amount": t.amount,
                    "currency": t.currency,
                    "label": t.label,
                    "partner_erp_id": t.partner_erp_id,
                    "partner_name": t.partner_name,
                    "counterpart_account": t.counterpart_account,
                    "transaction_type": t.transaction_type,
                    "is_reconciled": t.is_reconciled,
                    "erp_write_date": t.write_date,
                }
                for t in batch.records
                if t.company_erp_id in companies and t.bank_account_erp_id in accounts
            ]
            _upsert(self.session, BankTransaction, rows)
            state.cursor = batch.cursor
            total += len(rows)
        state.last_run_at = datetime.now(UTC)
        return total

    def _open_item_row(self, companies: dict[int, uuid.UUID], i: ErpOpenItem) -> dict:
        return {
            **self.base,
            "erp_id": i.erp_id,
            "company_id": companies[i.company_erp_id],
            "kind": i.kind,
            "number": i.number,
            "reference": i.reference,
            "partner_erp_id": i.partner_erp_id,
            "partner_name": i.partner_name,
            "invoice_date": i.invoice_date,
            "due_date": i.due_date,
            "currency": i.currency,
            "amount_total": i.amount_total,
            "amount_residual": i.amount_residual,
            "payment_state": i.payment_state,
            "is_open": i.is_open,
            "erp_write_date": i.write_date,
        }

    def sync_open_items(self) -> int:
        companies = _id_map(self.session, Company, self.conn)
        state = _state(self.session, self.conn, STREAM_OPEN_ITEMS)
        total = 0
        for batch in self.connector.open_items(state.cursor):
            rows = [
                self._open_item_row(companies, i)
                for i in batch.records
                if i.company_erp_id in companies
            ]
            _upsert(self.session, OpenItem, rows)
            state.cursor = batch.cursor
            total += len(rows)
        state.last_run_at = datetime.now(UTC)
        return total

    def refresh_open_items(self) -> int:
        """Re-read every item the mirror holds as open; close the ones paid or deleted."""
        companies = _id_map(self.session, Company, self.conn)
        open_ids = list(
            self.session.scalars(
                select(OpenItem.erp_id).where(
                    OpenItem.erp_connection_id == self.conn.id, OpenItem.is_open.is_(True)
                )
            )
        )
        refreshed = 0
        for start in range(0, len(open_ids), REFRESH_CHUNK):
            chunk = open_ids[start : start + REFRESH_CHUNK]
            items = self.connector.open_items_by_ids(chunk)
            _upsert(
                self.session,
                OpenItem,
                [self._open_item_row(companies, i) for i in items if i.company_erp_id in companies],
            )
            missing = set(chunk) - {i.erp_id for i in items}
            if missing:
                self.session.execute(
                    update(OpenItem)
                    .where(OpenItem.erp_connection_id == self.conn.id, OpenItem.erp_id.in_(missing))
                    .values(is_open=False, payment_state="deleted")
                )
            refreshed += len(chunk)
        return refreshed
