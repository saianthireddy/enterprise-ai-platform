"""SQLite-backed user store.

Previously an in-memory dict, which meant every restart wiped registered users
and re-issued new ids for the demo accounts. Same public interface as before, so
no caller changed.

Demo-user seeding is idempotent: it inserts only what is missing, so restarting
against an existing database neither raises nor resets a password an operator
has since changed.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone  # noqa: UP017

from app.auth.security import hash_password
from app.config import settings
from app.models.schemas import Role
from app.services.db import Database

DEMO_USERS = [
    ("admin@enterprise-ai.demo", "ChangeMe123!", "Platform Admin", Role.ADMIN),
    ("analyst@enterprise-ai.demo", "ChangeMe123!", "Demo Analyst", Role.USER),
]


def _row_to_user(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    user = dict(row)
    user["created_at"] = datetime.fromisoformat(user["created_at"])
    return user


class UserStore:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database(settings.database_url)
        self._seed_demo_users()

    def _seed_demo_users(self) -> None:
        for email, password, full_name, role in DEMO_USERS:
            if self.get_by_email(email) is None:
                self.create(email=email, password=password, full_name=full_name, role=role)

    def create(self, email: str, password: str, full_name: str, role: Role = Role.USER) -> dict:
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)  # noqa: UP017
        try:
            self.db.execute(
                "INSERT INTO users (id, email, full_name, role, password_hash, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, email, full_name, role.value, hash_password(password), created_at.isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            # UNIQUE(email) is the real guard now, not a pre-read — two
            # concurrent registrations of the same address can no longer both win.
            raise ValueError(f"User with email {email} already exists") from exc
        return {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role": role.value,
            "password_hash": hash_password(password),
            "created_at": created_at,
        }

    def get_by_id(self, user_id: str) -> dict | None:
        return _row_to_user(self.db.query_one("SELECT * FROM users WHERE id = ?", (user_id,)))

    def get_by_email(self, email: str) -> dict | None:
        return _row_to_user(self.db.query_one("SELECT * FROM users WHERE email = ?", (email,)))

    def get_or_create_oauth_user(self, email: str, full_name: str) -> dict:
        existing = self.get_by_email(email)
        if existing:
            return existing
        return self.create(email=email, password=uuid.uuid4().hex, full_name=full_name)

    def count(self) -> int:
        row = self.db.query_one("SELECT COUNT(*) AS n FROM users")
        return int(row["n"]) if row else 0


user_store = UserStore()
