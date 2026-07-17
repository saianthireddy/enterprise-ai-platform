"""Authentication endpoints: signup, login, Google OAuth, current user."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.oauth import build_authorization_url, exchange_code_for_profile
from app.auth.rbac import get_current_user
from app.auth.security import create_access_token, verify_password
from app.models.schemas import OAuthLoginRequest, Token, UserCreate, UserOut
from app.services.user_store import user_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate) -> UserOut:
    if user_store.get_by_email(payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = user_store.create(
        email=payload.email, password=payload.password, full_name=payload.full_name
    )
    return UserOut(**{k: user[k] for k in ("id", "email", "full_name", "role", "created_at")})


@router.post("/login", response_model=Token)
def login(email: str, password: str) -> Token:
    user = user_store.get_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    token, expires_in = create_access_token(subject=user["id"], role=user["role"])
    return Token(access_token=token, expires_in=expires_in)


@router.get("/oauth/google/authorize")
def google_authorize(redirect_uri: str) -> dict:
    state = uuid.uuid4().hex
    return {"authorization_url": build_authorization_url(redirect_uri, state), "state": state}


@router.post("/oauth/google/callback", response_model=Token)
def google_callback(payload: OAuthLoginRequest) -> Token:
    profile = exchange_code_for_profile(payload.code)
    user = user_store.get_or_create_oauth_user(profile["email"], profile["full_name"])
    token, expires_in = create_access_token(subject=user["id"], role=user["role"])
    return Token(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)) -> UserOut:
    return UserOut(**{k: user[k] for k in ("id", "email", "full_name", "role", "created_at")})
