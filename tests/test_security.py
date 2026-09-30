"""Security regressions: each test pins a hole that existed and was closed.

1. Demo accounts (public passwords) were created in every environment.
2. A placeholder SECRET_KEY let anyone forge an admin token.
3. Any user could read or append to any other user's conversation.
4. Login credentials travelled in the URL query string.
5. The SQL whitelist missed comma joins, so SQLite internals were reachable.
"""
from __future__ import annotations

import dataclasses
import sqlite3

import pytest
from app.auth import routes as auth_routes
from app.config import Settings, check_runtime_settings
from app.services.conversation import ConversationStore
from app.services.db import Database
from app.services.user_store import UserStore
from fastapi.testclient import TestClient

from ai.agents.sql_agent import SQLAgent, _authorizer, run_readonly, validate_sql
from scripts.seed_demo_db import seed

DEMO_ADMIN = "admin@enterprise-ai.demo"


# --------------------------------------------------------------- 1. demo users


def test_demo_users_are_not_created_when_seeding_is_off(tmp_path):
    store = UserStore(Database(f"sqlite:///{tmp_path / 'prod.db'}"), seed_demo_users=False)
    assert store.get_by_email(DEMO_ADMIN) is None
    assert store.count() == 0


@pytest.mark.parametrize(
    ("environment", "flag", "expected"),
    [
        ("development", None, True),
        ("production", None, False),
        ("staging", None, False),
        ("production", "true", True),  # explicit opt-in still possible
        ("development", "false", False),
    ],
)
def test_demo_seeding_defaults_to_development_only(monkeypatch, environment, flag, expected):
    monkeypatch.setenv("ENVIRONMENT", environment)
    if flag is None:
        monkeypatch.delenv("SEED_DEMO_USERS", raising=False)
    else:
        monkeypatch.setenv("SEED_DEMO_USERS", flag)
    assert Settings().seed_demo_users is expected


# ------------------------------------------------------------- 2. JWT secret


@pytest.mark.parametrize("secret", ["dev-secret-change-me", "replace-with-a-strong-random-value", "", "short-but-real"])
def test_placeholder_or_short_secret_is_refused_outside_development(secret):
    settings = dataclasses.replace(Settings(), environment="production", secret_key=secret, seed_demo_users=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_runtime_settings(settings)


def test_strong_secret_passes_in_production():
    settings = dataclasses.replace(Settings(), environment="production", secret_key="x" * 48, seed_demo_users=False)
    assert check_runtime_settings(settings) == []


def test_placeholder_secret_only_warns_in_development():
    settings = dataclasses.replace(Settings(), environment="development", secret_key="dev-secret-change-me")
    warnings = check_runtime_settings(settings)
    assert any("SECRET_KEY" in w for w in warnings)


# ------------------------------------------------------- 3. conversation owner


def _token(client: TestClient, email: str, password: str = "Str0ngPassw0rd!") -> str:
    client.post("/api/v1/auth/signup", json={"email": email, "password": password, "full_name": email})
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_other_users_cannot_read_a_conversation(client: TestClient):
    alice = {"Authorization": f"Bearer {_token(client, 'alice@example.com')}"}
    mallory = {"Authorization": f"Bearer {_token(client, 'mallory@example.com')}"}

    conv_id = client.post("/api/v1/chat", json={"message": "private question"}, headers=alice).json()["conversation_id"]

    assert client.get(f"/api/v1/chat/{conv_id}/history", headers=alice).status_code == 200
    assert client.get(f"/api/v1/chat/{conv_id}/history", headers=mallory).status_code == 404


def test_other_users_cannot_append_to_a_conversation(client: TestClient):
    alice = {"Authorization": f"Bearer {_token(client, 'alice2@example.com')}"}
    mallory = {"Authorization": f"Bearer {_token(client, 'mallory2@example.com')}"}
    conv_id = client.post("/api/v1/chat", json={"message": "hello"}, headers=alice).json()["conversation_id"]

    for path in ("/api/v1/chat", "/api/v1/chat/stream"):
        resp = client.post(path, json={"conversation_id": conv_id, "message": "injected"}, headers=mallory)
        assert resp.status_code == 404, path

    contents = [m["content"] for m in client.get(f"/api/v1/chat/{conv_id}/history", headers=alice).json()]
    assert "injected" not in contents


def test_unknown_conversation_id_starts_a_new_owned_thread(client: TestClient):
    alice = {"Authorization": f"Bearer {_token(client, 'alice3@example.com')}"}
    resp = client.post("/api/v1/chat", json={"conversation_id": "does-not-exist", "message": "hi"}, headers=alice)
    new_id = resp.json()["conversation_id"]
    assert new_id != "does-not-exist"
    assert client.get(f"/api/v1/chat/{new_id}/history", headers=alice).status_code == 200


def test_pre_ownership_database_is_migrated_and_legacy_threads_are_private(tmp_path):
    path = tmp_path / "old.db"
    legacy = sqlite3.connect(path)
    legacy.execute("CREATE TABLE conversations (id TEXT PRIMARY KEY, summary TEXT, created_at TEXT NOT NULL)")
    legacy.execute("INSERT INTO conversations VALUES ('legacy', NULL, '2026-01-01T00:00:00+00:00')")
    legacy.commit()
    legacy.close()

    store = ConversationStore(Database(f"sqlite:///{path}"))
    assert store.exists("legacy")
    assert not store.is_owned_by("legacy", "anyone")
    owned = store.create(owner_id="u1")
    assert store.is_owned_by(owned, "u1") and not store.is_owned_by(owned, "u2")


# ------------------------------------------------------------ 4. login in body


def test_login_rejects_credentials_in_the_query_string(client: TestClient):
    resp = client.post("/api/v1/auth/login", params={"username": DEMO_ADMIN, "password": "ChangeMe123!"})
    assert resp.status_code == 422


def test_oauth_stub_is_disabled_outside_development(client: TestClient, monkeypatch):
    monkeypatch.setattr(auth_routes, "settings", dataclasses.replace(auth_routes.settings, environment="production"))
    resp = client.post("/api/v1/auth/oauth/google/callback", json={"code": "anything"})
    assert resp.status_code == 501


# ------------------------------------------------------------------ 5. SQL


@pytest.fixture()
def demo_db(tmp_path):
    path = tmp_path / "demo.db"
    seed(path)
    return path


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name, sql FROM employees, sqlite_master",
        "SELECT * FROM employees e, orders o, secrets s",
        "SELECT * FROM employees; DELETE FROM employees",
        "SELECT load_extension('x') FROM employees",
        'SELECT * FROM "sqlite_master"',
        "SELECT * FROM employees WHERE id IN (SELECT id FROM secrets)",
    ],
)
def test_bypass_attempts_are_rejected_before_and_during_execution(demo_db, sql):
    with pytest.raises(ValueError):
        validate_sql(sql)
    with pytest.raises(ValueError):
        run_readonly(demo_db, sql)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT name FROM sqlite_master",
        "SELECT * FROM employees, sqlite_master",
        "SELECT random() FROM employees",
    ],
)
def test_authorizer_refuses_even_if_the_regex_is_bypassed(demo_db, sql):
    conn = sqlite3.connect(demo_db.resolve().as_uri() + "?mode=ro", uri=True)
    conn.set_authorizer(_authorizer)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute(sql).fetchall()


def test_agent_connection_is_read_only(demo_db):
    conn = sqlite3.connect(demo_db.resolve().as_uri() + "?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("DELETE FROM employees")


def test_templated_queries_still_work_under_the_authorizer(demo_db):
    agent = SQLAgent(db_path=demo_db)
    for question in [
        "how many open tickets are there?",
        "tickets by status",
        "top employees by revenue",
        "total revenue",
        "employees in engineering",
    ]:
        result = agent.run(question)
        assert result.metadata["sql"], question
        assert "rows" in result.metadata, question
