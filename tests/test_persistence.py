"""Persistence: the point of this layer is surviving a restart, so that is what
these assert — a second store instance opened against the same file, which is
exactly what a process restart looks like to SQLite.
"""
from __future__ import annotations

import logging
import threading

import pytest
from app.models.schemas import ChatMessage, ChatMessageRole, Role
from app.services.conversation import MAX_HISTORY_TURNS, SUMMARY_TRIGGER_TURNS, ConversationStore
from app.services.db import Database, resolve_path
from app.services.user_store import UserStore


@pytest.fixture()
def db_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'app.db'}"


# ------------------------------------------------------------------ resolve_path


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:///data/app.db", "data/app.db"),
        ("sqlite:///:memory:", ":memory:"),
        (":memory:", ":memory:"),
        ("sqlite:////abs/path.db", "/abs/path.db"),
    ],
)
def test_resolve_path_forms(url, expected):
    assert resolve_path(url) == expected


def test_unusable_database_url_falls_back_to_memory_with_a_warning(caplog):
    """A typo in DATABASE_URL should degrade, not stop the platform booting."""
    with caplog.at_level(logging.WARNING):
        assert resolve_path("postgres://user@host/db") == ":memory:"
    assert "not a sqlite:// URL" in caplog.text


def test_schema_is_created_on_connect(db_url):
    db = Database(db_url)
    tables = {r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "conversations", "messages", "documents"} <= tables


# -------------------------------------------------------------------- UserStore


def test_users_survive_a_restart(db_url):
    first = UserStore(Database(db_url))
    created = first.create(email="ada@example.com", password="hunter2hunter2", full_name="Ada")

    reopened = UserStore(Database(db_url))  # same file, new process
    found = reopened.get_by_email("ada@example.com")
    assert found is not None
    assert found["id"] == created["id"], "user id must be stable across restarts"
    assert found["full_name"] == "Ada"
    assert found["role"] == Role.USER.value


def test_demo_seeding_is_idempotent(db_url):
    db = Database(db_url)
    first = UserStore(db)
    admin_id = first.get_by_email("admin@enterprise-ai.demo")["id"]
    baseline = first.count()

    reopened = UserStore(db)  # must not raise, must not duplicate

    assert reopened.count() == baseline
    assert reopened.get_by_email("admin@enterprise-ai.demo")["id"] == admin_id


def test_duplicate_email_is_rejected(db_url):
    store = UserStore(Database(db_url))
    store.create(email="dup@example.com", password="hunter2hunter2", full_name="First")
    with pytest.raises(ValueError, match="already exists"):
        store.create(email="dup@example.com", password="hunter2hunter2", full_name="Second")


def test_concurrent_registration_of_one_email_yields_one_user(db_url):
    """The UNIQUE constraint is the guard, not a check-then-insert race."""
    store = UserStore(Database(db_url))
    errors: list[Exception] = []
    created: list[dict] = []

    def register() -> None:
        try:
            created.append(
                store.create(email="race@example.com", password="hunter2hunter2", full_name="Race")
            )
        except ValueError as exc:
            errors.append(exc)

    threads = [threading.Thread(target=register) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(created) == 1
    assert len(errors) == 7
    assert store.count() == 3  # two demo users + one winner


def test_oauth_user_is_reused_not_duplicated(db_url):
    store = UserStore(Database(db_url))
    first = store.get_or_create_oauth_user("oauth@example.com", "OAuth User")
    again = store.get_or_create_oauth_user("oauth@example.com", "OAuth User")
    assert first["id"] == again["id"]


# ------------------------------------------------------------ ConversationStore


def test_conversation_history_survives_a_restart(db_url):
    first = ConversationStore(Database(db_url))
    conv_id = first.create()
    first.append(conv_id, ChatMessage(role=ChatMessageRole.USER, content="how do I install?"))
    first.append(conv_id, ChatMessage(role=ChatMessageRole.ASSISTANT, content="pip install it"))

    reopened = ConversationStore(Database(db_url))
    history = reopened.history(conv_id)
    assert [m.content for m in history] == ["how do I install?", "pip install it"]
    assert [m.role for m in history] == [ChatMessageRole.USER, ChatMessageRole.ASSISTANT]
    assert reopened.exists(conv_id)


def test_appending_to_an_unknown_id_creates_the_thread(db_url):
    """Matches the old dict setdefault behaviour, which callers relied on."""
    store = ConversationStore(Database(db_url))
    store.append("adopted-id", ChatMessage(role=ChatMessageRole.USER, content="hi"))
    assert store.exists("adopted-id")
    assert len(store.history("adopted-id")) == 1


def test_history_is_trimmed_to_the_newest_turns(db_url):
    store = ConversationStore(Database(db_url))
    conv_id = store.create()
    for i in range(MAX_HISTORY_TURNS + 5):
        store.append(conv_id, ChatMessage(role=ChatMessageRole.USER, content=f"q{i}"))

    history = store.history(conv_id)
    assert len(history) == MAX_HISTORY_TURNS
    assert history[0].content == "q5", "oldest turns are the ones dropped"
    assert history[-1].content == f"q{MAX_HISTORY_TURNS + 4}"


def test_summary_is_written_at_the_trigger_and_persists(db_url):
    first = ConversationStore(Database(db_url))
    conv_id = first.create()
    for i in range(SUMMARY_TRIGGER_TURNS - 1):
        first.append(conv_id, ChatMessage(role=ChatMessageRole.USER, content=f"q{i}"))
    assert first.memory(conv_id) == "", "no summary before the trigger"

    first.append(conv_id, ChatMessage(role=ChatMessageRole.USER, content="q-trigger"))
    assert first.memory(conv_id) != ""

    reopened = ConversationStore(Database(db_url))
    assert reopened.memory(conv_id) == first.memory(conv_id)


def test_unknown_conversation_reads_are_empty_not_errors(db_url):
    store = ConversationStore(Database(db_url))
    assert store.history("nope") == []
    assert store.memory("nope") == ""
    assert store.exists("nope") is False


# ---------------------------------------------------------------- DocumentStore


def test_document_metadata_survives_a_restart(client, admin_headers, tmp_path):
    """Goes through the API so the wiring is covered, not just the store."""
    from app.dependencies import document_service
    from app.services.db import Database as DB

    meta = document_service.ingest(
        filename="guide.txt",
        content=b"Installing the widget requires a licence key.",
        content_type="text/plain",
        uploaded_by="admin@enterprise-ai.demo",
    )

    reopened = type(document_service)(
        document_service.retriever,
        document_service.embedder,
        DB(f"sqlite:///{document_service.db.path}"),
    )
    found = reopened.get(meta.doc_id)
    assert found is not None
    assert found.filename == "guide.txt"
    assert found.chunk_count == meta.chunk_count
    assert meta.doc_id in {d.doc_id for d in reopened.list_documents()}
