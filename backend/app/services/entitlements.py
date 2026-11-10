"""Which modules each company has contracted (billing: per company and module)."""

import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Company, Entitlement, Module
from app.models.billing import MODULE_REQUIRES


class ModuleNotSubscribed(Exception):
    def __init__(self, module: Module, company_id: uuid.UUID):
        super().__init__(f"Module {module.value!r} is not active for company {company_id}")
        self.module = module
        self.company_id = company_id


def active_modules(session: Session, day: date | None = None) -> dict[uuid.UUID, set[Module]]:
    """Map company id -> modules usable today (dependencies taken into account)."""
    day = day or date.today()
    rows = session.execute(
        select(Entitlement.company_id, Entitlement.module).where(
            Entitlement.valid_from <= day,
            or_(Entitlement.valid_to.is_(None), Entitlement.valid_to >= day),
        )
    ).all()
    contracted: dict[uuid.UUID, set[Module]] = {}
    for company_id, module in rows:
        contracted.setdefault(company_id, set()).add(Module(module))
    return {
        company_id: {m for m in modules if MODULE_REQUIRES.get(m, set()) <= modules}
        for company_id, modules in contracted.items()
    }


def companies_with_module(
    session: Session, module: Module, day: date | None = None
) -> list[uuid.UUID]:
    return [cid for cid, mods in active_modules(session, day).items() if module in mods]


def require_module(
    session: Session, module: Module, company_id: uuid.UUID, day: date | None = None
) -> None:
    if module not in active_modules(session, day).get(company_id, set()):
        raise ModuleNotSubscribed(module, company_id)


def grant(
    session: Session,
    company: Company,
    module: Module,
    valid_from: date,
    valid_to: date | None = None,
    is_trial: bool = False,
) -> Entitlement:
    ent = Entitlement(
        tenant_id=company.tenant_id,
        company_id=company.id,
        module=module,
        valid_from=valid_from,
        valid_to=valid_to,
        is_trial=is_trial,
    )
    session.add(ent)
    session.flush()
    return ent
