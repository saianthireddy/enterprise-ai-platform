"""SQLite-backed conversation history + a rolling-summary "memory".

Was in-memory, so a restart lost every thread mid-conversation. Interface is
unchanged; the trimming behaviour is now expressed as a delete of the oldest
rows rather than a list slice, and the summary is a column on the conversation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone  # noqa: UP017

from app.config import settings
from app.models.schemas import ChatMessage, ChatMessageRole
from app.services.db import Database

MAX_HISTORY_TURNS = 20
SUMMARY_TRIGGER_TURNS = 12


class ConversationStore:
    def __init__(self, db: Database | None = None) -> None:
        self.db = db or Database(settings.database_url)

    def create(self) -> str:
        conv_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO conversations (id, summary, created_at) VALUES (?, NULL, ?)",
            (conv_id, datetime.now(timezone.utc).isoformat()),  # noqa: UP017
        )
        return conv_id

    def _ensure(self, conversation_id: str) -> None:
        """append() used to create the thread implicitly via setdefault; keep that."""
        self.db.execute(
            "INSERT OR IGNORE INTO conversations (id, summary, created_at) VALUES (?, NULL, ?)",
            (conversation_id, datetime.now(timezone.utc).isoformat()),  # noqa: UP017
        )

    def append(self, conversation_id: str, message: ChatMessage) -> None:
        self._ensure(conversation_id)
        self.db.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, message.role.value, message.content, message.created_at.isoformat()),
        )

        total = self._message_count(conversation_id)
        if total >= SUMMARY_TRIGGER_TURNS and not self.memory(conversation_id):
            summary = self._summarize(self.history(conversation_id))
            self.db.execute(
                "UPDATE conversations SET summary = ? WHERE id = ?", (summary, conversation_id)
            )
        if total > MAX_HISTORY_TURNS:
            # Keep the newest MAX_HISTORY_TURNS. Summary is written first above,
            # so trimming never silently discards context that was never summarised.
            self.db.execute(
                "DELETE FROM messages WHERE conversation_id = ? AND id NOT IN ("
                "  SELECT id FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?"
                ")",
                (conversation_id, conversation_id, MAX_HISTORY_TURNS),
            )

    def _message_count(self, conversation_id: str) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?", (conversation_id,)
        )
        return int(row["n"]) if row else 0

    def _summarize(self, history: list[ChatMessage]) -> str:
        user_turns = [m.content for m in history if m.role == ChatMessageRole.USER]
        return f"Earlier in this conversation, the user asked about: {'; '.join(user_turns[:5])}"

    def history(self, conversation_id: str) -> list[ChatMessage]:
        rows = self.db.query(
            "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        )
        return [
            ChatMessage(
                role=ChatMessageRole(r["role"]),
                content=r["content"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def memory(self, conversation_id: str) -> str:
        row = self.db.query_one("SELECT summary FROM conversations WHERE id = ?", (conversation_id,))
        return (row["summary"] or "") if row else ""

    def exists(self, conversation_id: str) -> bool:
        return self.db.query_one("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)) is not None


conversation_store = ConversationStore()
