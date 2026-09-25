"""Shared FastAPI dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session

from app.core.db import get_session
from app.core.security import ACCESS, JWTError, decode_token
from app.models import User, UserRole

# tokenUrl points at the login route so /docs shows the password flow.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# auto_error=False → no token simply means "anonymous", not a 401.
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

_DISABLED_EXC = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    try:
        payload = decode_token(token)
    except JWTError:
        raise _CREDENTIALS_EXC

    # Only access tokens unlock routes — a refresh token must not.
    if payload.get("type") != ACCESS:
        raise _CREDENTIALS_EXC

    sub = payload.get("sub")
    if sub is None:
        raise _CREDENTIALS_EXC

    user = session.get(User, int(sub))
    if user is None:
        raise _CREDENTIALS_EXC
    # Read on every request, so disabling an account takes effect on its very
    # next call rather than when its access token expires.
    if not user.is_active:
        raise _DISABLED_EXC
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User | None:
    """Resolve the user if a valid access token is present, else None.

    Used by public endpoints that show extra data to authenticated/admin users
    (e.g. drafts in the catalog) but stay open to anonymous visitors. A bad token
    is treated as anonymous, not an error.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != ACCESS:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    user = session.get(User, int(sub))
    # A disabled account browses like anyone else: public pages, no drafts.
    return user if user is not None and user.is_active else None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
