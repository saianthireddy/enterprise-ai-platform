"""Test fixtures: put repo root + backend on sys.path exactly like main.py does,
then hand back a fresh TestClient per test module."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        params={"email": "admin@enterprise-ai.demo", "password": "ChangeMe123!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def user_token(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        params={"email": "analyst@enterprise-ai.demo", "password": "ChangeMe123!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def auth_headers(user_token: str) -> dict:
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture()
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
