"""In-memory conversation history + a simple rolling-summary "memory"."""
from __future__ import annotations

import threading
import uuid

from app.models.schemas import ChatMessage, ChatMessageRole

MAX_HISTORY_TURNS = 20
SUMMARY_TRIGGER_TURNS = 12


class ConversationStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conversations: dict[str, list[ChatMessage]] = {}
        self._summaries: dict[str, str] = {}

    def create(self) -> str:
        conv_id = str(uuid.uuid4())
        with self._lock:
            self._conversations[conv_id] = []
        return conv_id

    def append(self, conversation_id: str, message: ChatMessage) -> None:
        with self._lock:
            history = self._conversations.setdefault(conversation_id, [])
            history.append(message)
            if len(history) > MAX_HISTORY_TURNS:
                self._conversations[conversation_id] = history[-MAX_HISTORY_TURNS:]
            if len(history) >= SUMMARY_TRIGGER_TURNS and conversation_id not in self._summaries:
                self._summaries[conversation_id] = self._summarize(history)

    def _summarize(self, history: list[ChatMessage]) -> str:
        user_turns = [m.content for m in history if m.role == ChatMessageRole.USER]
        return f"Earlier in this conversation, the user asked about: {'; '.join(user_turns[:5])}"

    def history(self, conversation_id: str) -> list[ChatMessage]:
        return list(self._conversations.get(conversation_id, []))

    def memory(self, conversation_id: str) -> str:
        return self._summaries.get(conversation_id, "")

    def exists(self, conversation_id: str) -> bool:
        return conversation_id in self._conversations


conversation_store = ConversationStore()
