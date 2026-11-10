"""Liquidity module (Fase 1 base): bank accounts, transactions, open items, position."""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.api.schemas import (
    BankAccountOut,
    BankTransactionOut,
    CurrencyTotal,
    OpenItemOut,
    PositionOut,
)
from app.models import BankAccount, BankTransaction, Module, OpenItem
from app.services.entitlements import companies_with_module

router = APIRouter(tags=["liquidity"])


def _allowed_companies(session, company_id: uuid.UUID | None) -> list[uuid.UUID]:
    allowed = companies_with_module(session, Module.LIQUIDITY)
    if company_id is None:
        return allowed
    if company_id not in allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {"code": "module_not_subscribed", "module": Module.LIQUIDITY.value},
        )
    return [company_id]


@router.get("/bank-accounts", response_model=list[BankAccountOut])
def list_bank_accounts(session: SessionDep, company_id: uuid.UUID | None = None):
    companies = _allowed_companies(session, company_id)
    return session.scalars(
        select(BankAccount)
        .where(BankAccount.company_id.in_(companies), BankAccount.active.is_(True))
        .order_by(BankAccount.name)
    ).all()


@router.get("/bank-transactions", response_model=list[BankTransactionOut])
def list_bank_transactions(
    session: SessionDep,
    company_id: uuid.UUID | None = None,
    bank_account_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    companies = _allowed_companies(session, company_id)
    q = select(BankTransaction).where(BankTransaction.company_id.in_(companies))
    if bank_account_id:
        q = q.where(BankTransaction.bank_account_id == bank_account_id)
    if date_from:
        q = q.where(BankTransaction.date >= date_from)
    if date_to:
        q = q.where(BankTransaction.date <= date_to)
    q = q.order_by(BankTransaction.date.desc(), BankTransaction.erp_id.desc())
    return session.scalars(q.limit(limit).offset(offset)).all()


@router.get("/open-items", response_model=list[OpenItemOut])
def list_open_items(
    session: SessionDep,
    company_id: uuid.UUID | None = None,
    kind: str | None = Query(None, pattern="^(receivable|payable)$"),
    limit: int = Query(200, le=1000),
    offset: int = 0,
):
    companies = _allowed_companies(session, company_id)
    q = select(OpenItem).where(OpenItem.company_id.in_(companies), OpenItem.is_open.is_(True))
    if kind:
        q = q.where(OpenItem.kind == kind)
    q = q.order_by(OpenItem.due_date.asc().nulls_last(), OpenItem.erp_id)
    return session.scalars(q.limit(limit).offset(offset)).all()


@router.get("/position", response_model=PositionOut)
def cash_position(session: SessionDep, company_id: uuid.UUID | None = None):
    companies = _allowed_companies(session, company_id)
    accounts = session.scalars(
        select(BankAccount)
        .where(BankAccount.company_id.in_(companies), BankAccount.active.is_(True))
        .order_by(BankAccount.name)
    ).all()
    open_totals = session.execute(
        select(OpenItem.currency, OpenItem.kind, func.sum(OpenItem.amount_residual))
        .where(OpenItem.company_id.in_(companies), OpenItem.is_open.is_(True))
        .group_by(OpenItem.currency, OpenItem.kind)
    ).all()

    totals: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"balance": Decimal(0), "receivables": Decimal(0), "payables": Decimal(0)}
    )
    for acc in accounts:
        totals[acc.currency]["balance"] += acc.balance
    for currency, kind, amount in open_totals:
        totals[currency]["receivables" if kind == "receivable" else "payables"] += amount or 0

    as_of = min((a.balance_at for a in accounts if a.balance_at), default=None)
    return PositionOut(
        as_of=as_of,
        totals=[CurrencyTotal(currency=c, **v) for c, v in sorted(totals.items())],
        accounts=[BankAccountOut.model_validate(a) for a in accounts],
    )
