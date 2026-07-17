"""In-memory analytics aggregation feeding the admin dashboard.

A real deployment persists these events to a time-series store (e.g.
Postgres + a materialized view, or Prometheus); the interface is identical.
"""
from __future__ import annotations

import threading
from collections import defaultdict

from app.middleware.cost_tracking import estimate_cost_usd, estimate_tokens
from app.models.schemas import AnalyticsSnapshot


class AnalyticsService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_by_agent: dict[str, int] = defaultdict(int)
        self._latencies_ms: list[float] = []
        self._tokens_total = 0
        self._search_hits = 0
        self._search_total = 0
        self._active_user_ids: set[str] = set()

    def record_request(
        self, agent: str, latency_ms: float, response_text: str, user_id: str, had_citations: bool
    ) -> int:
        tokens = estimate_tokens(response_text)
        with self._lock:
            self._requests_by_agent[agent] += 1
            self._latencies_ms.append(latency_ms)
            self._tokens_total += tokens
            self._active_user_ids.add(user_id)
            self._search_total += 1
            if had_citations:
                self._search_hits += 1
        return tokens

    def snapshot(self) -> AnalyticsSnapshot:
        with self._lock:
            avg_latency = (
                sum(self._latencies_ms) / len(self._latencies_ms) if self._latencies_ms else 0.0
            )
            accuracy = self._search_hits / self._search_total if self._search_total else 0.0
            return AnalyticsSnapshot(
                active_users=len(self._active_user_ids),
                ai_requests_total=sum(self._requests_by_agent.values()),
                token_usage_total=self._tokens_total,
                estimated_cost_usd=estimate_cost_usd(self._tokens_total),
                avg_latency_ms=round(avg_latency, 2),
                search_accuracy=round(accuracy, 4),
                requests_by_agent=dict(self._requests_by_agent),
            )


analytics_service = AnalyticsService()
