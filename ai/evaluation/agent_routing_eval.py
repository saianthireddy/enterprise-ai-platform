"""Accuracy of the intent router against a labeled query set."""
from __future__ import annotations

from dataclasses import dataclass

from ai.agents.orchestrator import classify


@dataclass
class RoutingCase:
    query: str
    expected_agent: str


def evaluate_routing(cases: list[RoutingCase]) -> float:
    if not cases:
        return 0.0
    correct = sum(1 for c in cases if classify(c.query) == c.expected_agent)
    return round(correct / len(cases), 4)


DEFAULT_ROUTING_SUITE: list[RoutingCase] = [
    RoutingCase("How many open tickets are there?", "sql"),
    RoutingCase("Draft a reply to this customer email", "email"),
    RoutingCase("Give me a weekly summary report", "report"),
    RoutingCase("Review this Python function for bugs", "code"),
    RoutingCase("What does the uploaded PDF say about refunds?", "document"),
    RoutingCase("What's our vacation policy?", "knowledge_base"),
]
