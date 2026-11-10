"""Authentication: platform-issued JWTs turned into a ``Principal``.

The platform is its own token issuer (HS256, ``SDT_JWT_SECRET``). Users get a token by:
- logging in from Odoo (``/auth/odoo-sso``, see ``app/core/sso.py``): the MVP path, no
  external identity provider needed;
- the development login (``/auth/dev-token``), only in dev/test.

Claims: ``sub`` user, ``tenant_id``, ``roles`` (list), ``companies`` (list of company UUIDs
the user may see; absent = all companies of the tenant).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings, get_settings

TENANT_ROLES = {"admin", "treasurer", "approver", "viewer"}
# SmallDev staff only (module activation, support). Never implied by a tenant role.
PLATFORM_ROLES = {"platform_admin"}
ROLES = TENANT_ROLES | PLATFORM_ROLES
ISSUER = "sdtreasury"


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: UUID
    roles: frozenset[str] = field(default_factory=frozenset)
    # None means every company of the tenant.
    company_ids: frozenset[UUID] | None = None

    def has_role(self, *roles: str) -> bool:
        """True if the principal has any of ``roles``; tenant ``admin`` implies every
        tenant role but no platform role."""
        wanted = set(roles)
        if self.roles & wanted:
            return True
        return "admin" in self.roles and bool(wanted & TENANT_ROLES)

    def can_see(self, company_id: UUID) -> bool:
        return self.company_ids is None or company_id in self.company_ids


def issue_token(
    tenant_id: UUID,
    user_id: str,
    roles: list[str],
    company_ids: list[UUID] | None = None,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "sub": user_id,
        "tenant_id": str(tenant_id),
        "roles": sorted(set(roles) & ROLES),
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_ttl_hours),
    }
    if company_ids is not None:
        claims["companies"] = [str(c) for c in company_ids]
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def issue_dev_token(tenant_id: UUID, user_id: str, roles: list[str], settings: Settings) -> str:
    if not settings.dev_login_enabled:
        raise AuthError("Dev tokens are disabled in this environment")
    return issue_token(tenant_id, user_id, roles, settings=settings)


def decode_token(token: str, settings: Settings | None = None) -> Principal:
    settings = settings or get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
        tenant_id = UUID(claims["tenant_id"])
        companies = claims.get("companies")
        company_ids = frozenset(UUID(c) for c in companies) if companies is not None else None
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise AuthError(f"Invalid token: {exc}") from exc
    roles = frozenset(r for r in claims.get("roles", []) if r in ROLES)
    return Principal(
        user_id=claims["sub"], tenant_id=tenant_id, roles=roles, company_ids=company_ids
    )
