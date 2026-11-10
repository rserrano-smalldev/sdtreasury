"""Odoo 18 mapping, using responses shaped like real Odoo 18 search_read output."""

import json
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.connectors.odoo.client import OdooClient, OdooError
from app.connectors.odoo.connector import OdooConnector


class FakeOdoo:
    """Answers execute_kw calls per (model, method)."""

    def __init__(self, data: dict):
        self.data = data
        self.calls: list[tuple] = []
        self.context: dict = {}
        self.uid = 2

    def version(self):
        return {"server_version": "18.0+e"}

    def execute_kw(self, model, method, args, kwargs=None):
        self.calls.append((model, method, args, kwargs))
        handler = self.data[(model, method)]
        return handler(args, kwargs) if callable(handler) else handler

    def search_read(self, model, domain, fields, *, order=None, limit=None, offset=0):
        self.calls.append((model, "search_read", domain, {"limit": limit, "offset": offset}))
        rows = self.data[(model, "search_read")]
        rows = rows(domain) if callable(rows) else rows
        return rows[offset : offset + limit] if limit else rows


BASE = {
    ("res.users", "read"): [{"id": 2, "company_ids": [1]}],
    ("res.company", "search_read"): [
        {"id": 1, "name": "Small Development SL", "vat": "ESB00000000", "currency_id": [125, "EUR"]}
    ],
}


def test_bank_accounts_and_balances():
    odoo = FakeOdoo(
        {
            **BASE,
            ("account.journal", "search_read"): lambda domain: (
                [
                    {
                        "id": 27,
                        "default_account_id": [500, "572001 Santander"],
                        "currency_id": [125, "EUR"],
                        "company_id": [1, "Small Development SL"],
                    }
                ]
                if domain[0][0] == "id"
                else [
                    {
                        "id": 27,
                        "name": "Santander",
                        "bank_account_id": [9, "ES12 3456 7890"],
                        "bank_id": [2, "Banco Santander - BSCHESMMXXX"],
                        "currency_id": [125, "EUR"],
                        "company_id": [1, "Small Development SL"],
                        "bank_statements_source": "online_sync",
                        "active": True,
                        "write_date": "2026-11-01 08:00:00",
                    },
                    {
                        "id": 34,
                        "name": "Banco",
                        "bank_account_id": False,
                        "bank_id": False,
                        "currency_id": False,
                        "company_id": [1, "Small Development SL"],
                        "bank_statements_source": "undefined",
                        "active": True,
                        "write_date": "2026-01-01 08:00:00",
                    },
                ]
            ),
            ("res.partner.bank", "search_read"): [{"id": 9, "acc_number": "ES12 3456 7890"}],
            ("account.move.line", "read_group"): [{"balance": 12345.678, "__count": 10}],
        }
    )
    connector = OdooConnector(odoo)
    accounts = connector.bank_accounts()
    assert [a.name for a in accounts] == ["Santander", "Banco"]
    assert accounts[0].iban == "ES1234567890"
    assert accounts[0].bank_name == "Banco Santander - BSCHESMMXXX"
    assert accounts[1].currency == "EUR"  # falls back to company currency
    assert odoo.context["allowed_company_ids"] == [1]

    balances = connector.bank_balances([27])
    assert balances[0].balance == Decimal("12345.68")
    _, _, args, _ = next(c for c in odoo.calls if c[1] == "read_group")
    assert ["account_id", "=", 500] in args[0]
    assert args[1] == ["balance:sum"]


def test_statement_lines_are_paginated_with_cursor():
    lines = [
        {
            "id": i,
            "date": f"2026-11-0{i % 9 + 1}",
            "amount": -12.5,
            "payment_ref": "RECIBO",
            "partner_id": [7, "Proveedor SL"],
            "partner_name": False,
            "account_number": "ES99",
            "journal_id": [27, "Santander"],
            "company_id": [1, "Small Development SL"],
            "currency_id": [125, "EUR"],
            "transaction_type": False,
            "is_reconciled": i % 2 == 0,
            "write_date": f"2026-11-05 10:00:{i:02d}",
        }
        for i in range(5)
    ]
    odoo = FakeOdoo({**BASE, ("account.bank.statement.line", "search_read"): lines})
    batches = list(OdooConnector(odoo, page_size=2).bank_transactions("2026-11-01 00:00:00"))
    assert [len(b.records) for b in batches] == [2, 2, 1]
    assert batches[-1].cursor == "2026-11-05 10:00:04"
    first = batches[0].records[0]
    assert first.amount == Decimal("-12.50")
    assert first.partner_name == "Proveedor SL"
    assert first.date == date(2026, 11, 1)
    domain = next(c[2] for c in odoo.calls if c[0] == "account.bank.statement.line")
    assert ["write_date", ">=", "2026-11-01 00:00:00"] in domain


def _move(id_, move_type, state="posted", payment_state="not_paid", residual=100.0):
    return {
        "id": id_,
        "name": f"F/{id_}",
        "ref": False,
        "move_type": move_type,
        "state": state,
        "payment_state": payment_state,
        "commercial_partner_id": [7, "Cliente SA"],
        "invoice_date": "2026-10-01",
        "invoice_date_due": "2026-11-30",
        "amount_total_signed": residual,
        "amount_residual_signed": residual,
        "company_id": [1, "Small Development SL"],
        "write_date": "2026-11-01 00:00:00",
    }


def test_open_items_mapping():
    moves = [
        _move(1, "out_invoice"),
        _move(2, "in_invoice", residual=-50.0),
        _move(3, "out_invoice", payment_state="paid", residual=0.0),
        _move(4, "in_refund", state="cancel", residual=10.0),
    ]
    odoo = FakeOdoo({**BASE, ("account.move", "search_read"): moves})
    items = {i.erp_id: i for b in OdooConnector(odoo).open_items(None) for i in b.records}
    assert items[1].kind == "receivable" and items[1].is_open
    assert items[2].kind == "payable" and items[2].amount_residual == Decimal("-50.00")
    assert not items[3].is_open
    assert not items[4].is_open
    assert items[1].due_date == date(2026, 11, 30)


def test_client_authenticates_and_raises_odoo_errors():
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append(body["params"])
        if body["params"]["method"] == "authenticate":
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": 2})
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {"message": "Odoo Server Error", "data": {"message": "Access Denied"}},
            },
        )

    client = OdooClient(
        "http://odoo.internal/",
        "db",
        "api@test",
        "secret",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(OdooError, match="Access Denied"):
        client.search_read("res.partner", [], ["name"])
    assert seen[0]["args"] == ["db", "api@test", "secret", {}]
    assert seen[1]["args"][:5] == ["db", 2, "secret", "res.partner", "search_read"]
