"""Companies, entitlements, sync and (dev-only) token issuing."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import PrincipalDep, SessionDep, require_role
from app.api.schemas import CompanyOut, EntitlementIn, EntitlementOut, SyncOut
from app.connectors.registry import build_connector
from app.core import sso
from app.core.auth import TENANT_ROLES, AuthError, issue_dev_token, issue_token
from app.core.config import get_settings
from app.core.db import platform_session, tenant_session
from app.core.secrets import SecretNotFound, resolve_secret
from app.models import Company, Entitlement, ErpConnection, SsoNonce, Tenant
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


class OdooSsoIn(BaseModel):
    token: str


def _sso_reject(reason: str) -> HTTPException:
    # Same message for every failure; the reason only goes to the server log.
    import logging

    logging.getLogger(__name__).warning("Odoo SSO rejected: %s", reason)
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Login from Odoo failed")


@router.post("/auth/odoo-sso", tags=["auth"])
def odoo_sso(body: OdooSsoIn):
    """Exchange a launch token signed by the Odoo addon for a platform token."""
    try:
        claimed = sso.peek(body.token)
    except sso.SsoError as exc:
        raise _sso_reject(str(exc)) from exc

    with platform_session() as session:
        tenant = session.scalar(
            select(Tenant).where(Tenant.slug == claimed["tenant"], Tenant.active.is_(True))
        )
    if tenant is None:
        raise _sso_reject("unknown tenant")

    with tenant_session(tenant.id) as session:
        query = select(ErpConnection).where(
            ErpConnection.active.is_(True), ErpConnection.sso_secret_ref.is_not(None)
        )
        if claimed.get("db"):
            query = query.where(ErpConnection.database == claimed["db"])
        conn = session.scalars(query).first()
        if conn is None:
            raise _sso_reject("no SSO-enabled connection")
        try:
            payload = sso.verify(body.token, resolve_secret(conn.sso_secret_ref))
        except (sso.SsoError, SecretNotFound) as exc:
            raise _sso_reject(str(exc)) from exc
        company_ids = list(
            session.scalars(
                select(Company.id).where(
                    Company.erp_connection_id == conn.id,
                    Company.erp_id.in_([int(c) for c in payload.get("company_ids", [])]),
                )
            )
        )

    with platform_session() as session:
        session.execute(delete(SsoNonce).where(SsoNonce.expires_at < datetime.now(UTC)))
    try:
        with platform_session() as session:
            session.add(
                SsoNonce(
                    jti=str(payload["jti"]),
                    expires_at=datetime.fromtimestamp(float(payload["exp"]) + 60, UTC),
                )
            )
    except IntegrityError as exc:
        raise _sso_reject("token already used") from exc

    # Odoo can only grant tenant roles, never platform roles.
    roles = [r for r in payload.get("roles", []) if r in TENANT_ROLES] or ["viewer"]
    token = issue_token(tenant.id, f"odoo:{payload['login']}", roles, company_ids)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"name": payload.get("name"), "email": payload.get("email")},
    }


@router.get("/me", tags=["auth"])
def me(principal: PrincipalDep):
    return {
        "user_id": principal.user_id,
        "tenant_id": principal.tenant_id,
        "roles": sorted(principal.roles),
        "company_ids": sorted(map(str, principal.company_ids))
        if principal.company_ids is not None
        else None,
    }


@router.get("/companies", response_model=list[CompanyOut], tags=["platform"])
def list_companies(session: SessionDep, principal: PrincipalDep):
    modules = active_modules(session)
    companies = [
        c
        for c in session.scalars(
            select(Company).where(Company.active.is_(True)).order_by(Company.name)
        )
        if principal.can_see(c.id)
    ]
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
