"""Trains a TF-IDF + Logistic Regression intent router as a learned upgrade
over the rule-based `classify()` in ai/agents/orchestrator.py, registers it
via ModelRegistry, and promotes it to production only if it beats the
current champion (challenger/champion pattern, same as enterprise-mlops-platform).
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ai.evaluation.model_registry import ModelRegistry

# Small synthetic training set, expanded from the routing eval suite so the
# router generalizes past the exact eval phrasing.
TRAINING_DATA: list[tuple[str, str]] = [
    ("How many open tickets do we have?", "sql"),
    ("What's our total revenue this quarter?", "sql"),
    ("Count the tickets by priority", "sql"),
    ("List employees in the Sales department", "sql"),
    ("Draft a reply to this angry customer email", "email"),
    ("Write a response to the billing complaint", "email"),
    ("Reply to this thread about the outage", "email"),
    ("Give me a weekly summary report", "report"),
    ("Summarize this month's usage metrics", "report"),
    ("Generate a report on agent performance", "report"),
    ("Review this Python function for bugs", "code"),
    ("Refactor this JavaScript snippet", "code"),
    ("Explain what this code does", "code"),
    ("What does the uploaded PDF say about refunds?", "document"),
    ("Summarize the attached contract", "document"),
    ("Find the clause about termination in this file", "document"),
    ("What's our vacation policy?", "knowledge_base"),
    ("How do I reset my VPN access?", "knowledge_base"),
    ("What's the process for expense approval?", "knowledge_base"),
]


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(stop_words="english")),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )


def train_and_register(registry: ModelRegistry | None = None) -> dict:
    registry = registry or ModelRegistry()
    texts = [t for t, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.3, random_state=42, stratify=labels
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    accuracy = pipeline.score(X_test, y_test)

    challenger = registry.register("intent_router", pipeline, metrics={"accuracy": accuracy})

    champion = registry.load_production("intent_router")
    champion_accuracy = None
    if champion is not None:
        champion_accuracy = champion.score(X_test, y_test)

    if champion_accuracy is None or accuracy >= champion_accuracy:
        registry.promote("intent_router", challenger.version, "production")
        promoted = True
    else:
        promoted = False

    return {
        "version": challenger.version,
        "accuracy": accuracy,
        "champion_accuracy": champion_accuracy,
        "promoted": promoted,
    }


if __name__ == "__main__":
    result = train_and_register()
    print(f"Trained intent_router v{result['version']}: accuracy={result['accuracy']:.3f}, "
          f"promoted={result['promoted']}")
