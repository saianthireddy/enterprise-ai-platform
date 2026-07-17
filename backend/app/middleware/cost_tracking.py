"""Token usage / cost estimation helpers.

Pricing table is intentionally simple (USD per 1K tokens) and configurable
without redeploying, matching how the admin dashboard reports estimated spend.
"""
from __future__ import annotations

PRICE_PER_1K_TOKENS_USD = 0.0015


def estimate_tokens(text: str) -> int:
    # Rough heuristic (~4 chars/token) avoids requiring a tokenizer dependency.
    return max(1, len(text) // 4)


def estimate_cost_usd(tokens: int) -> float:
    return round((tokens / 1000) * PRICE_PER_1K_TOKENS_USD, 6)
