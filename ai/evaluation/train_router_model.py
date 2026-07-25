"""Trains a TF-IDF + Logistic Regression intent router as a learned upgrade
over the rule-based `classify()` in ai/agents/orchestrator.py, registers it
via ModelRegistry, and promotes it to production only if it beats the
current champion (challenger/champion pattern, same as enterprise-mlops-platform).

Evaluation notes
----------------
The headline metric is 5-fold stratified cross-validation over the whole
dataset, not a single holdout: with a corpus this size one holdout split is
worth several percentage points per sample, so a lone accuracy number is
mostly sampling noise. The holdout is kept only as the common yardstick for
scoring challenger and champion against identical data.

Promotion is strictly greater-than. An equal score is not an improvement, and
because the training corpus is fixed, a tie is exactly what a re-run with no
new data produces — it should leave the incumbent in place.
"""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

from ai.evaluation.model_registry import ModelRegistry

RANDOM_STATE = 42
CV_FOLDS = 5
TEST_SIZE = 0.25

# Labelled utterances for the six agent intents. Expanded well past the routing
# eval suite so the classifier learns intent vocabulary rather than memorising
# the eval phrasing — each intent deliberately mixes imperative ("draft a…"),
# interrogative ("what is…") and elliptical ("vacation policy?") forms, since
# real users type all three.
TRAINING_DATA: list[tuple[str, str]] = [
    # -- sql: aggregate/lookup questions answerable from structured tables ----
    ("How many open tickets do we have?", "sql"),
    ("What's our total revenue this quarter?", "sql"),
    ("Count the tickets by priority", "sql"),
    ("List employees in the Sales department", "sql"),
    ("How many users signed up last month?", "sql"),
    ("Show me the top 10 customers by spend", "sql"),
    ("What is the average resolution time for tickets?", "sql"),
    ("Break down orders by region", "sql"),
    ("How many tickets are still unassigned?", "sql"),
    ("Total number of active subscriptions", "sql"),
    ("Which product has the highest sales volume?", "sql"),
    ("Sum the invoice amounts for December", "sql"),
    ("How many employees joined this year?", "sql"),
    ("Give me the count of failed payments", "sql"),
    ("What percentage of tickets were closed on time?", "sql"),
    ("Rank departments by headcount", "sql"),
    ("How many orders shipped yesterday?", "sql"),
    ("Average order value by month", "sql"),
    ("Number of refunds issued last week", "sql"),
    ("Query the database for churned accounts", "sql"),
    # -- email: drafting outbound correspondence -----------------------------
    ("Draft a reply to this angry customer email", "email"),
    ("Write a response to the billing complaint", "email"),
    ("Reply to this thread about the outage", "email"),
    ("Compose an email apologising for the delay", "email"),
    ("Draft a follow-up message to the client", "email"),
    ("Write a polite decline to this vendor", "email"),
    ("Send a response thanking them for the feedback", "email"),
    ("Draft an email confirming the meeting time", "email"),
    ("Write back to the customer asking for more details", "email"),
    ("Compose a note to the team about the release", "email"),
    ("Reply to this escalation from the account manager", "email"),
    ("Draft a message explaining the refund process", "email"),
    ("Write an email introducing our new support hours", "email"),
    ("Respond to this request for a quote", "email"),
    ("Draft a courteous reply rejecting the proposal", "email"),
    ("Write a message chasing the overdue invoice", "email"),
    ("Compose an apology email for the shipping error", "email"),
    ("Reply confirming we received their documents", "email"),
    ("Draft an email scheduling a follow-up call", "email"),
    ("Write a response to this negative review", "email"),
    # -- report: narrative summaries over analytics --------------------------
    ("Give me a weekly summary report", "report"),
    ("Summarize this month's usage metrics", "report"),
    ("Generate a report on agent performance", "report"),
    ("Produce a quarterly business review deck", "report"),
    ("Create an executive summary of support trends", "report"),
    ("Write up the monthly analytics overview", "report"),
    ("Generate a dashboard summary for leadership", "report"),
    ("Summarise how the platform performed this week", "report"),
    ("Build a report on customer satisfaction scores", "report"),
    ("Give me a rundown of this quarter's highlights", "report"),
    ("Produce an overview of ticket volume trends", "report"),
    ("Create a summary report of API usage", "report"),
    ("Write a status report for the steering committee", "report"),
    ("Generate insights from last month's data", "report"),
    ("Summarise cost and token usage for the period", "report"),
    ("Prepare a performance report with recommendations", "report"),
    ("Give me a digest of key metrics", "report"),
    ("Compile a report on agent response times", "report"),
    ("Draft an analytics summary with next steps", "report"),
    ("Overview report of platform adoption", "report"),
    # -- code: reviewing, explaining, refactoring source ---------------------
    ("Review this Python function for bugs", "code"),
    ("Refactor this JavaScript snippet", "code"),
    ("Explain what this code does", "code"),
    ("Is there a security issue in this function?", "code"),
    ("Clean up this method and add type hints", "code"),
    ("Why does this loop throw an exception?", "code"),
    ("Optimise this database query in the ORM", "code"),
    ("Add docstrings to this class", "code"),
    ("What does this regular expression match?", "code"),
    ("Spot the bug in this sorting algorithm", "code"),
    ("Rewrite this using a list comprehension", "code"),
    ("Check this snippet for bare except clauses", "code"),
    ("Explain this stack trace", "code"),
    ("Convert this callback code to async await", "code"),
    ("Review my pull request diff", "code"),
    ("Simplify this nested conditional", "code"),
    ("Is this function thread safe?", "code"),
    ("Suggest unit tests for this module", "code"),
    ("Find the memory leak in this script", "code"),
    ("Explain the time complexity of this implementation", "code"),
    # -- document: questions scoped to one uploaded file ---------------------
    ("What does the uploaded PDF say about refunds?", "document"),
    ("Summarize the attached contract", "document"),
    ("Find the clause about termination in this file", "document"),
    ("What are the payment terms in this agreement?", "document"),
    ("Pull the key dates out of this document", "document"),
    ("Does the attached policy cover remote work?", "document"),
    ("Summarise the uploaded spreadsheet", "document"),
    ("What is the liability cap in this contract?", "document"),
    ("Extract the action items from these meeting notes", "document"),
    ("What does page 4 of the PDF say?", "document"),
    ("Find the renewal date in the attached file", "document"),
    ("Summarise this uploaded presentation", "document"),
    ("Which sections of this document mention security?", "document"),
    ("What is the notice period in this attachment?", "document"),
    ("Read the uploaded invoice and tell me the total", "document"),
    ("Does this document specify a governing law?", "document"),
    ("Summarise the attached technical specification", "document"),
    ("What warranties are listed in this file?", "document"),
    ("Extract the pricing table from the uploaded PDF", "document"),
    ("Explain the confidentiality clause in this contract", "document"),
    # -- knowledge_base: org-wide policy and how-to lookups ------------------
    ("What's our vacation policy?", "knowledge_base"),
    ("How do I reset my VPN access?", "knowledge_base"),
    ("What's the process for expense approval?", "knowledge_base"),
    ("Where do I submit a timesheet?", "knowledge_base"),
    ("How do I request new equipment?", "knowledge_base"),
    ("What are the company holidays this year?", "knowledge_base"),
    ("Who do I contact about payroll questions?", "knowledge_base"),
    ("How does the referral bonus work?", "knowledge_base"),
    ("What is the remote work policy?", "knowledge_base"),
    ("How do I enrol in the health plan?", "knowledge_base"),
    ("What's the procedure for reporting an incident?", "knowledge_base"),
    ("How much parental leave am I entitled to?", "knowledge_base"),
    ("Where can I find the onboarding checklist?", "knowledge_base"),
    ("What is the policy on business travel?", "knowledge_base"),
    ("How do I book a conference room?", "knowledge_base"),
    ("What's the escalation path for outages?", "knowledge_base"),
    ("How do I get access to the staging environment?", "knowledge_base"),
    ("What are the guidelines for using company laptops?", "knowledge_base"),
    ("Who approves purchase requests?", "knowledge_base"),
    ("What's the dress code for client meetings?", "knowledge_base"),
]

INTENTS = sorted({label for _, label in TRAINING_DATA})


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, C=10.0, random_state=RANDOM_STATE)),
        ]
    )


def cross_validated_accuracy(texts: list[str], labels: list[str]) -> tuple[float, float]:
    """Mean and standard deviation of stratified k-fold accuracy."""
    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_val_score(build_pipeline(), texts, labels, cv=folds, scoring="accuracy")
    return float(np.mean(scores)), float(np.std(scores))


def train_and_register(registry: ModelRegistry | None = None) -> dict:
    registry = registry or ModelRegistry()
    texts = [t for t, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]

    cv_mean, cv_std = cross_validated_accuracy(texts, labels)

    # Common yardstick: challenger and champion are scored on the same holdout,
    # so the promotion comparison is like-for-like.
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=labels
    )
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    accuracy = pipeline.score(X_test, y_test)

    challenger = registry.register(
        "intent_router",
        pipeline,
        metrics={
            "accuracy": accuracy,
            "cv_accuracy_mean": cv_mean,
            "cv_accuracy_std": cv_std,
            "n_samples": float(len(texts)),
        },
    )

    champion = registry.load_production("intent_router")
    champion_accuracy = None
    if champion is not None:
        champion_accuracy = champion.score(X_test, y_test)

    # Strictly greater: a tie is what an unchanged corpus produces, and that is
    # not a reason to churn production.
    if champion_accuracy is None or accuracy > champion_accuracy:
        registry.promote("intent_router", challenger.version, "production")
        promoted = True
    else:
        promoted = False

    return {
        "version": challenger.version,
        "accuracy": accuracy,
        "cv_accuracy_mean": cv_mean,
        "cv_accuracy_std": cv_std,
        "champion_accuracy": champion_accuracy,
        "promoted": promoted,
    }


if __name__ == "__main__":
    result = train_and_register()
    print(
        f"Trained intent_router v{result['version']}: "
        f"holdout={result['accuracy']:.3f}, "
        f"cv={result['cv_accuracy_mean']:.3f}+/-{result['cv_accuracy_std']:.3f}, "
        f"promoted={result['promoted']}"
    )
