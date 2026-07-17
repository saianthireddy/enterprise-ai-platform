"""Natural-language -> SQL agent with a hard read-only safety boundary.

Demo schema: employees, tickets, orders. The safety guard rejects anything
that is not a single SELECT statement touching only whitelisted tables —
this runs even if a real LLM produced the SQL, so it's the actual security
boundary, not just a prompt instruction.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from ai.agents.base import AgentResult, BaseAgent

ALLOWED_TABLES = {"employees", "tickets", "orders"}
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|PRAGMA|REPLACE)\b", re.IGNORECASE
)

DEMO_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "demo.db"

# Deterministic NL -> SQL mapping for the offline demo corpus. A real deployment
# swaps this for an LLM call, still passing through `validate_sql` below.
INTENT_TEMPLATES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"how many (open )?tickets", re.I), "SELECT COUNT(*) AS open_tickets FROM tickets WHERE status = 'open'"),
    (re.compile(r"tickets? by (priority|status)", re.I), "SELECT status, COUNT(*) AS count FROM tickets GROUP BY status"),
    (re.compile(r"top.*employees?.*(revenue|sales)", re.I), (
        "SELECT e.full_name, SUM(o.amount) AS total_revenue FROM orders o "
        "JOIN employees e ON e.id = o.employee_id GROUP BY e.full_name "
        "ORDER BY total_revenue DESC LIMIT 5"
    )),
    (re.compile(r"total (revenue|sales|orders)", re.I), "SELECT SUM(amount) AS total_revenue, COUNT(*) AS order_count FROM orders"),
    (re.compile(r"employees? in (\w+)", re.I), "SELECT full_name, department FROM employees WHERE department = :dept"),
]


def validate_sql(sql: str) -> None:
    stripped = sql.strip().rstrip(";")
    if not stripped.upper().startswith("SELECT"):
        raise ValueError("Only SELECT statements are permitted")
    if FORBIDDEN_KEYWORDS.search(stripped):
        raise ValueError("Statement contains a forbidden keyword")
    tables_mentioned = set(re.findall(r"FROM\s+(\w+)|JOIN\s+(\w+)", stripped, re.IGNORECASE))
    flat = {t for pair in tables_mentioned for t in pair if t}
    if not flat.issubset(ALLOWED_TABLES):
        raise ValueError(f"Query references non-whitelisted table(s): {flat - ALLOWED_TABLES}")


class SQLAgent(BaseAgent):
    name = "sql"
    description = "Answers analytics questions by generating and running read-only SQL."
    capabilities = ["nl-to-sql", "read-only", "table-whitelisting"]

    def __init__(self, db_path: str | Path = DEMO_DB_PATH, **kwargs) -> None:
        super().__init__(**kwargs)
        self.db_path = Path(db_path)

    def _translate(self, query: str) -> str | None:
        for pattern, template in INTENT_TEMPLATES:
            match = pattern.search(query)
            if match:
                if ":dept" in template and match.groups():
                    return None  # handled with params in run()
                return template
        return None

    def run(self, query: str, context: dict[str, Any] | None = None) -> AgentResult:
        params: dict[str, Any] = {}
        sql = self._translate(query)
        dept_match = re.search(r"employees? in (\w+)", query, re.IGNORECASE)
        if dept_match:
            sql = "SELECT full_name, department FROM employees WHERE department = :dept"
            params = {"dept": dept_match.group(1).title()}

        if sql is None:
            return AgentResult(
                output=(
                    "I can answer questions about ticket volume, ticket status, "
                    "employee revenue, total revenue, or employees by department. "
                    "Try rephrasing, e.g. 'how many open tickets are there?'"
                ),
                metadata={"sql": None},
            )

        validate_sql(sql)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        rows_as_dicts = [dict(r) for r in rows]
        summary = "; ".join(
            ", ".join(f"{k}={v}" for k, v in row.items()) for row in rows_as_dicts
        ) or "No rows matched."
        return AgentResult(
            output=summary,
            metadata={"sql": sql, "params": params, "row_count": len(rows_as_dicts), "rows": rows_as_dicts},
        )
