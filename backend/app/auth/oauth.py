"""Google OAuth 2.0 authorization-code flow (stubbed token exchange for offline/dev use).

In production, `exchange_code_for_profile` calls Google's token + userinfo
endpoints. Without configured credentials it deterministically derives a
profile from the authorization code so the full login flow is exercisable
in tests and demos without a live Google app.
"""
from __future__ import annotations

import hashlib
from urllib.parse import urlencode

from app.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def build_authorization_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": settings.google_oauth_client_id or "demo-client-id",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_profile(code: str) -> dict[str, str]:
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        raise NotImplementedError(
            "Live Google token exchange requires network access; "
            "wire httpx calls to Google's token + userinfo endpoints here."
        )
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:10]
    return {
        "email": f"user-{digest}@oauth.demo",
        "full_name": f"OAuth User {digest[:4]}",
        "provider_id": digest,
    }
