"""Odoo 18 Enterprise implementation of ``ErpConnector``."""

from collections.abc import Iterator
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
from app.connectors.odoo.client import OdooClient

INVOICE_TYPES = {
    "out_invoice": "receivable",
    "out_refund": "receivable",
    "in_invoice": "payable",
    "in_refund": "payable",
}
OPEN_PAYMENT_STATES = {"not_paid", "partial", "in_payment"}
ODOO_DATETIME = "%Y-%m-%d %H:%M:%S"


def _m2o_id(value) -> int | None:
    return value[0] if value else None


def _m2o_name(value) -> str | None:
    return value[1] if value else None


def _str(value) -> str | None:
    return value or None


def _date(value) -> date | None:
    return date.fromisoformat(value) if value else None


def _dt(value) -> datetime | None:
    return datetime.strptime(value, ODOO_DATETIME) if value else None


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


class OdooConnector:
    STATEMENT_LINE_FIELDS = [
        "date",
        "amount",
        "payment_ref",
        "partner_id",
        "partner_name",
        "account_number",
        "journal_id",
        "company_id",
        "currency_id",
        "transaction_type",
        "is_reconciled",
        "write_date",
    ]
    MOVE_FIELDS = [
        "name",
        "ref",
        "move_type",
        "state",
        "payment_state",
        "commercial_partner_id",
        "invoice_date",
        "invoice_date_due",
        "amount_total_signed",
        "amount_residual_signed",
        "company_id",
        "write_date",
    ]

    def __init__(self, client: OdooClient, page_size: int = 500):
        self.client = client
        self.page_size = page_size
        self._company_currency: dict[int, str] = {}

    # -- setup -------------------------------------------------------------------------------

    def _ensure_company_context(self) -> None:
        """Read across every company the technical user is allowed to see."""
        if "allowed_company_ids" in self.client.context:
            return
        user = self.client.execute_kw(
            "res.users", "read", [[self.client.uid]], {"fields": ["company_ids"]}
        )[0]
        self.client.context["allowed_company_ids"] = user["company_ids"]

    def test_connection(self) -> dict:
        version = self.client.version()
        self._ensure_company_context()
        return {
            "server_version": version.get("server_version"),
            "uid": self.client.uid,
            "company_ids": self.client.context["allowed_company_ids"],
        }

    # -- master data -------------------------------------------------------------------------

    def companies(self) -> list[ErpCompany]:
        self._ensure_company_context()
        rows = self.client.search_read(
            "res.company",
            [["id", "in", self.client.context["allowed_company_ids"]]],
            ["name", "vat", "currency_id"],
        )
        result = []
        for row in rows:
            currency = _m2o_name(row["currency_id"]) or "EUR"
            self._company_currency[row["id"]] = currency
            result.append(
                ErpCompany(
                    erp_id=row["id"], name=row["name"], vat=_str(row["vat"]), currency=currency
                )
            )
        return result

    def _currency_of_company(self, company_id: int) -> str:
        if not self._company_currency:
            self.companies()
        return self._company_currency.get(company_id, "EUR")

    def bank_accounts(self) -> list[ErpBankAccount]:
        self._ensure_company_context()
        journals = self.client.search_read(
            "account.journal",
            [["type", "=", "bank"], ["active", "in", [True, False]]],
            [
                "name",
                "bank_account_id",
                "bank_id",
                "currency_id",
                "company_id",
                "bank_statements_source",
                "active",
                "write_date",
            ],
        )
        bank_ids = [j["bank_account_id"][0] for j in journals if j["bank_account_id"]]
        ibans: dict[int, str] = {}
        if bank_ids:
            for acc in self.client.search_read(
                "res.partner.bank", [["id", "in", bank_ids]], ["acc_number"]
            ):
                ibans[acc["id"]] = (acc["acc_number"] or "").replace(" ", "") or None
        result = []
        for j in journals:
            company_id = j["company_id"][0]
            result.append(
                ErpBankAccount(
                    erp_id=j["id"],
                    company_erp_id=company_id,
                    name=j["name"],
                    iban=ibans.get(_m2o_id(j["bank_account_id"])),
                    bank_name=_m2o_name(j["bank_id"]),
                    currency=_m2o_name(j["currency_id"]) or self._currency_of_company(company_id),
                    sync_source=_str(j["bank_statements_source"]),
                    active=j["active"],
                    write_date=_dt(j["write_date"]),
                )
            )
        return result

    def bank_balances(self, bank_account_erp_ids: list[int]) -> list[ErpBankBalance]:
        """Book balance of each bank journal's default account (posted entries).

        In Odoo 17+ every statement line creates a posted entry on the bank account,
        so this equals the bank balance including unreconciled movements.
        """
        if not bank_account_erp_ids:
            return []
        self._ensure_company_context()
        journals = self.client.search_read(
            "account.journal",
            [["id", "in", bank_account_erp_ids], ["active", "in", [True, False]]],
            ["default_account_id", "currency_id", "company_id"],
        )
        result = []
        for j in journals:
            if not j["default_account_id"]:
                continue
            company_currency = self._currency_of_company(j["company_id"][0])
            journal_currency = _m2o_name(j["currency_id"]) or company_currency
            foreign = journal_currency != company_currency
            groups = self.client.execute_kw(
                "account.move.line",
                "read_group",
                [
                    [
                        ["account_id", "=", j["default_account_id"][0]],
                        ["parent_state", "=", "posted"],
                        ["company_id", "=", j["company_id"][0]],
                    ],
                    ["amount_currency:sum" if foreign else "balance:sum"],
                    [],
                ],
                {"lazy": False},
            )
            total = groups[0].get("amount_currency" if foreign else "balance") if groups else 0
            result.append(
                ErpBankBalance(
                    bank_account_erp_id=j["id"], balance=_money(total), currency=journal_currency
                )
            )
        return result

    # -- incremental streams -----------------------------------------------------------------

    def _paginate(self, model: str, domain: list, fields: list[str]) -> Iterator[list[dict]]:
        offset = 0
        while True:
            rows = self.client.search_read(
                model,
                domain,
                fields,
                order="write_date asc, id asc",
                limit=self.page_size,
                offset=offset,
            )
            if not rows:
                return
            yield rows
            if len(rows) < self.page_size:
                return
            offset += self.page_size

    @staticmethod
    def _since_domain(since: str | None) -> list:
        # ">=" plus idempotent upserts: records written in the same second as the
        # cursor are re-read rather than missed.
        return [["write_date", ">=", since]] if since else []

    def bank_transactions(self, since: str | None) -> Iterator[Batch[ErpBankTransaction]]:
        self._ensure_company_context()
        domain = [["journal_id.type", "=", "bank"], *self._since_domain(since)]
        for rows in self._paginate(
            "account.bank.statement.line", domain, self.STATEMENT_LINE_FIELDS
        ):
            records = [self._map_statement_line(r) for r in rows]
            yield Batch(records=records, cursor=rows[-1]["write_date"])

    def _map_statement_line(self, r: dict) -> ErpBankTransaction:
        company_id = r["company_id"][0]
        return ErpBankTransaction(
            erp_id=r["id"],
            bank_account_erp_id=r["journal_id"][0],
            company_erp_id=company_id,
            date=_date(r["date"]),
            amount=_money(r["amount"]),
            currency=_m2o_name(r["currency_id"]) or self._currency_of_company(company_id),
            label=_str(r["payment_ref"]),
            partner_erp_id=_m2o_id(r["partner_id"]),
            partner_name=_m2o_name(r["partner_id"]) or _str(r["partner_name"]),
            counterpart_account=_str(r["account_number"]),
            transaction_type=_str(r["transaction_type"]),
            is_reconciled=bool(r["is_reconciled"]),
            write_date=_dt(r["write_date"]),
        )

    def open_items(self, since: str | None) -> Iterator[Batch[ErpOpenItem]]:
        self._ensure_company_context()
        # Include cancelled/paid documents so the mirror can close items it holds as open.
        domain = [
            ["move_type", "in", list(INVOICE_TYPES)],
            ["state", "in", ["posted", "cancel"]],
            *self._since_domain(since),
        ]
        for rows in self._paginate("account.move", domain, self.MOVE_FIELDS):
            yield Batch(records=[self._map_move(r) for r in rows], cursor=rows[-1]["write_date"])

    def open_items_by_ids(self, erp_ids: list[int]) -> list[ErpOpenItem]:
        """Re-read specific documents, used to catch payment_state changes that do not
        bump ``write_date`` (stored computed fields recomputed on reconciliation).
        Documents deleted in Odoo are simply absent from the result."""
        if not erp_ids:
            return []
        self._ensure_company_context()
        rows = self.client.search_read("account.move", [["id", "in", erp_ids]], self.MOVE_FIELDS)
        return [self._map_move(r) for r in rows]

    def _map_move(self, r: dict) -> ErpOpenItem:
        company_id = r["company_id"][0]
        residual = _money(r["amount_residual_signed"])
        return ErpOpenItem(
            erp_id=r["id"],
            company_erp_id=company_id,
            kind=INVOICE_TYPES[r["move_type"]],
            number=_str(r["name"]) if r["name"] != "/" else None,
            reference=_str(r["ref"]),
            partner_erp_id=_m2o_id(r["commercial_partner_id"]),
            partner_name=_m2o_name(r["commercial_partner_id"]),
            invoice_date=_date(r["invoice_date"]),
            due_date=_date(r["invoice_date_due"]),
            currency=self._currency_of_company(company_id),
            amount_total=_money(r["amount_total_signed"]),
            amount_residual=residual,
            payment_state=_str(r["payment_state"]),
            is_open=(
                r["state"] == "posted"
                and r["payment_state"] in OPEN_PAYMENT_STATES
                and residual != 0
            ),
            write_date=_dt(r["write_date"]),
        )
