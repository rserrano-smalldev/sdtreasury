from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import AuthError, Principal, decode_token
from app.core.db import SessionLocal, set_tenant

bearer = HTTPBearer(auto_error=False)


def get_principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_token(creds.credentials)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


def get_session(principal: Annotated[Principal, Depends(get_principal)]) -> Iterator[Session]:
    """Tenant-scoped session: RLS only lets this request see its own tenant's rows."""
    with SessionLocal() as session, session.begin():
        set_tenant(session, principal.tenant_id)
        yield session


def require_role(*roles: str):
    def checker(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not principal.has_role(*roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return principal

    return checker


PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]
