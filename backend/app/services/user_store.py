"""In-memory user store.

Swappable for a real database by implementing the same interface against
SQLAlchemy models; kept in-memory here so the whole platform runs and tests
without provisioning Postgres.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone  # noqa: UP017

from app.auth.security import hash_password
from app.models.schemas import Role


class UserStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users_by_id: dict[str, dict] = {}
        self._users_by_email: dict[str, str] = {}
        self._seed_demo_users()

    def _seed_demo_users(self) -> None:
        self.create(
            email="admin@enterprise-ai.demo",
            password="ChangeMe123!",
            full_name="Platform Admin",
            role=Role.ADMIN,
        )
        self.create(
            email="analyst@enterprise-ai.demo",
            password="ChangeMe123!",
            full_name="Demo Analyst",
            role=Role.USER,
        )

    def create(self, email: str, password: str, full_name: str, role: Role = Role.USER) -> dict:
        with self._lock:
            if email in self._users_by_email:
                raise ValueError(f"User with email {email} already exists")
            user_id = str(uuid.uuid4())
            user = {
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "role": role.value,
                "password_hash": hash_password(password),
                "created_at": datetime.now(timezone.utc),  # noqa: UP017
            }
            self._users_by_id[user_id] = user
            self._users_by_email[email] = user_id
            return user

    def get_by_id(self, user_id: str) -> dict | None:
        return self._users_by_id.get(user_id)

    def get_by_email(self, email: str) -> dict | None:
        user_id = self._users_by_email.get(email)
        return self._users_by_id.get(user_id) if user_id else None

    def get_or_create_oauth_user(self, email: str, full_name: str) -> dict:
        existing = self.get_by_email(email)
        if existing:
            return existing
        return self.create(email=email, password=uuid.uuid4().hex, full_name=full_name)

    def count(self) -> int:
        return len(self._users_by_id)


user_store = UserStore()
