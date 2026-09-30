"""Environment-driven application settings."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    app_name: str = "Enterprise AI Platform"
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-me")
    )
    access_token_expire_minutes: int = field(
        default_factory=lambda: int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    )
    jwt_algorithm: str = "HS256"

    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    )
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))

    vector_backend: str = field(default_factory=lambda: os.getenv("VECTOR_BACKEND", "memory"))
    pinecone_api_key: str = field(default_factory=lambda: os.getenv("PINECONE_API_KEY", ""))
    pinecone_index: str = field(default_factory=lambda: os.getenv("PINECONE_INDEX", "enterprise-ai"))

    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    google_oauth_client_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    )
    google_oauth_client_secret: str = field(
        default_factory=lambda: os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
    )

    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "25")))
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    )

    # The demo accounts have passwords published in the README, so they are
    # only created in development unless explicitly requested.
    seed_demo_users: bool = field(
        default_factory=lambda: _bool_env(
            "SEED_DEMO_USERS", os.getenv("ENVIRONMENT", "development") == "development"
        )
    )

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Placeholder values shipped in this repo. Anyone can read them, so a token
# signed with one of them can be forged by anyone.
KNOWN_PLACEHOLDER_SECRETS = frozenset({
    "",
    "dev-secret-change-me",
    "change-me-to-a-long-random-value",
    "replace-with-a-strong-random-value",
})
MIN_SECRET_LENGTH = 32


def check_runtime_settings(s: Settings) -> list[str]:
    """Refuse to run outside development with a forgeable JWT secret.

    Returns warnings for development; raises ``RuntimeError`` otherwise.
    """
    weak = s.secret_key in KNOWN_PLACEHOLDER_SECRETS or len(s.secret_key) < MIN_SECRET_LENGTH
    if weak and not s.is_development:
        raise RuntimeError(
            f"SECRET_KEY is a placeholder or shorter than {MIN_SECRET_LENGTH} characters. "
            "Set a long random value (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`) "
            f"before running with ENVIRONMENT={s.environment!r}."
        )
    warnings = []
    if weak:
        warnings.append("SECRET_KEY is a development placeholder; tokens can be forged. Never deploy with it.")
    if s.seed_demo_users and not s.is_development:
        warnings.append("SEED_DEMO_USERS is on outside development; the demo passwords are public.")
    return warnings


settings = Settings()
