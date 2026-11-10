"""Authentication: turn a bearer token into a ``Principal``.

Token claims used by the platform:
- ``sub``: user id
- ``custom:tenant_id`` (Cognito) or ``tenant_id`` (dev): tenant UUID
- ``custom:roles`` / ``roles``: comma-separated or list of roles
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

import jwt

from app.core.config import Settings, get_settings

TENANT_ROLES = {"admin", "treasurer", "approver", "viewer"}
# SmallDev staff only (module activation, support). Never implied by a tenant role.
PLATFORM_ROLES = {"platform_admin"}
ROLES = TENANT_ROLES | PLATFORM_ROLES


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: UUID
    roles: frozenset[str] = field(default_factory=frozenset)

    def has_role(self, *roles: str) -> bool:
        """True if the principal has any of ``roles``; tenant ``admin`` implies every
        tenant role but no platform role."""
        wanted = set(roles)
        if self.roles & wanted:
            return True
        return "admin" in self.roles and bool(wanted & TENANT_ROLES)


def _parse_roles(raw) -> frozenset[str]:
    if raw is None:
        return frozenset()
    items = raw.split(",") if isinstance(raw, str) else list(raw)
    return frozenset(r.strip() for r in items if r.strip() in ROLES)


def issue_dev_token(tenant_id: UUID, user_id: str, roles: list[str], settings: Settings) -> str:
    if settings.auth_mode != "dev" or settings.env not in ("dev", "test"):
        raise AuthError("Dev tokens are disabled in this environment")
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "tenant_id": str(tenant_id),
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(hours=12),
    }
    return jwt.encode(claims, settings.dev_jwt_secret, algorithm="HS256")


@lru_cache
def _jwks_client(region: str, pool_id: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    )


def decode_token(token: str, settings: Settings | None = None) -> Principal:
    settings = settings or get_settings()
    try:
        if settings.auth_mode == "dev":
            claims = jwt.decode(token, settings.dev_jwt_secret, algorithms=["HS256"])
        else:
            key = _jwks_client(settings.cognito_region, settings.cognito_user_pool_id)
            signing_key = key.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.cognito_app_client_id,
            )
    except jwt.PyJWTError as exc:
        raise AuthError(str(exc)) from exc

    tenant = claims.get("custom:tenant_id") or claims.get("tenant_id")
    if not tenant:
        raise AuthError("Token has no tenant")
    try:
        tenant_id = UUID(tenant)
    except ValueError as exc:
        raise AuthError("Invalid tenant id in token") from exc
    roles = _parse_roles(claims.get("custom:roles") or claims.get("roles"))
    return Principal(user_id=claims["sub"], tenant_id=tenant_id, roles=roles)
