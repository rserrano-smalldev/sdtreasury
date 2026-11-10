"""Companies, entitlements, sync and (dev-only) token issuing."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import PrincipalDep, SessionDep, require_role
from app.api.schemas import CompanyOut, EntitlementIn, EntitlementOut, SyncOut
from app.connectors.registry import build_connector
from app.core.auth import AuthError, issue_dev_token
from app.core.config import get_settings
from app.core.db import platform_session
from app.models import Company, Entitlement, ErpConnection, Tenant
from app.services.entitlements import active_modules, grant
from app.services.sync import SyncService

router = APIRouter()


class DevTokenIn(BaseModel):
    tenant_slug: str
    user_id: str = "dev@local"
    roles: list[str] = ["admin"]


@router.post("/auth/dev-token", tags=["auth"])
def dev_token(body: DevTokenIn):
    settings = get_settings()
    with platform_session() as session:
        tenant = session.scalar(select(Tenant).where(Tenant.slug == body.tenant_slug))
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown tenant")
    try:
        token = issue_dev_token(tenant.id, body.user_id, body.roles, settings)
    except AuthError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", tags=["auth"])
def me(principal: PrincipalDep):
    return {
        "user_id": principal.user_id,
        "tenant_id": principal.tenant_id,
        "roles": sorted(principal.roles),
    }


@router.get("/companies", response_model=list[CompanyOut], tags=["platform"])
def list_companies(session: SessionDep):
    modules = active_modules(session)
    companies = session.scalars(
        select(Company).where(Company.active.is_(True)).order_by(Company.name)
    ).all()
    return [
        CompanyOut(
            id=c.id,
            name=c.name,
            vat=c.vat,
            currency=c.currency,
            modules=sorted(modules.get(c.id, set())),
        )
        for c in companies
    ]


@router.get("/entitlements", response_model=list[EntitlementOut], tags=["platform"])
def list_entitlements(session: SessionDep):
    return session.scalars(select(Entitlement).order_by(Entitlement.valid_from)).all()


@router.post(
    "/entitlements",
    response_model=EntitlementOut,
    status_code=status.HTTP_201_CREATED,
    tags=["platform"],
    dependencies=[Depends(require_role("platform_admin"))],
)
def create_entitlement(body: EntitlementIn, session: SessionDep):
    company = session.get(Company, body.company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown company")
    return grant(session, company, body.module, body.valid_from, body.valid_to, body.is_trial)


@router.post(
    "/erp-connections/{connection_id}/sync",
    response_model=SyncOut,
    tags=["platform"],
    dependencies=[Depends(require_role("admin", "platform_admin"))],
)
def run_sync(connection_id: uuid.UUID, session: SessionDep):
    # Fase 0: synchronous. Moves to a queue worker (SQS) when webhooks arrive.
    conn = session.get(ErpConnection, connection_id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown ERP connection")
    report = SyncService(session, conn, build_connector(conn)).run()
    return SyncOut(**{k: v for k, v in vars(report).items() if k != "errors"})
