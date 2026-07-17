"""Redis-backed response cache for repeated agent queries.

Falls back to an in-process dict when REDIS_URL is unset, so caching is
exercised in tests without a live Redis instance.
"""
from __future__ import annotations

import json
from typing import Any


class RedisCache:
    def __init__(self, redis_url: str = "", ttl_seconds: int = 900) -> None:
        self.ttl_seconds = ttl_seconds
        self._fallback: dict[str, str] = {}
        self._client = None
        if redis_url:
            import redis  # imported lazily; optional dependency

            self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key) if self._client else self._fallback.get(key)
        return json.loads(raw) if raw else None

    def set(self, key: str, value: Any) -> None:
        raw = json.dumps(value)
        if self._client:
            self._client.setex(key, self.ttl_seconds, raw)
        else:
            self._fallback[key] = raw
