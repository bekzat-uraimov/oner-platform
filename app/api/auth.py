"""Auth routes: register, login, refresh, me."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.api.deps import CurrentUser
from app.core.db import get_session
from app.core.limiter import LOGIN_RATE_LIMIT, REGISTER_RATE_LIMIT, limiter
from app.core.security import (
    REFRESH,
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models import User
from app.schemas import RefreshRequest, Token, UserCreate, UserRead
from app.services.auth import EmailAlreadyRegistered, authenticate, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> Token:
    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(REGISTER_RATE_LIMIT)
def register(
    request: Request,  # required by slowapi to key the limit
    body: UserCreate,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    try:
        return register_user(session, body.email, body.password)
    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )


@router.post("/login", response_model=Token)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(
    request: Request,  # required by slowapi to key the limit
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    # OAuth2 form uses `username`; we treat it as the email.
    user = authenticate(session, form.username, form.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Checked only once the password matched, so "disabled" can't be used to
    # learn which emails have accounts.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
        )
    return _tokens_for(user)


@router.post("/refresh", response_model=Token)
def refresh(
    body: RefreshRequest,
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    if payload.get("type") != REFRESH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token"
        )

    user = session.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
        )
    return _tokens_for(user)


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> User:
    return current_user
