"""Natural-language -> SQL agent with a hard read-only safety boundary.

Demo schema: employees, tickets, orders. Two layers keep generated SQL
read-only and inside the whitelist, and both run even if a real LLM wrote the
query, so neither depends on a prompt instruction:

1. ``validate_sql`` rejects obvious problems early with a readable error.
2. The query then runs on a **read-only** connection with a SQLite authorizer
   that permits only SELECT, reads of whitelisted tables, and a fixed set of
   functions. The authorizer sees the statement SQLite actually compiled, so
   comma joins, subqueries and odd spellings that slip past a regex are still
   refused. It is the real security boundary.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from ai.agents.base import AgentResult, BaseAgent

ALLOWED_TABLES = {"employees", "tickets", "orders"}
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|REPLACE|VACUUM|LOAD_EXTENSION)\b", re.IGNORECASE
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


_TABLE_LIST = re.compile(
    r"\b(?:FROM|JOIN)\s+(.+?)(?=\b(?:WHERE|GROUP|ORDER|LIMIT|JOIN|ON|HAVING|UNION|INNER|LEFT|RIGHT|CROSS|OUTER|NATURAL)\b|\)|;|$)",
    re.IGNORECASE | re.DOTALL,
)

# Aggregates and scalar helpers the templates (and a reasonable LLM) need.
ALLOWED_FUNCTIONS = {
    "count", "sum", "avg", "min", "max", "round", "abs", "lower", "upper",
    "length", "coalesce", "ifnull", "date", "strftime", "substr", "trim",
}


def _referenced_tables(sql: str) -> set[str]:
    """Every table named after FROM/JOIN, including comma-separated lists."""
    tables: set[str] = set()
    for match in _TABLE_LIST.finditer(sql):
        for part in match.group(1).split(","):
            words = part.strip().lstrip("(").split()
            if words:
                tables.add(words[0].strip("`\"[]").lower())
    return tables


def validate_sql(sql: str) -> None:
    stripped = sql.strip().rstrip(";")
    if not stripped.upper().startswith("SELECT"):
        raise ValueError("Only SELECT statements are permitted")
    if ";" in stripped:
        raise ValueError("Only a single statement is permitted")
    if FORBIDDEN_KEYWORDS.search(stripped):
        raise ValueError("Statement contains a forbidden keyword")
    if "sqlite_" in stripped.lower():
        raise ValueError("SQLite internal tables are not queryable")
    tables = _referenced_tables(stripped)
    if not tables <= ALLOWED_TABLES:
        raise ValueError(f"Query references non-whitelisted table(s): {tables - ALLOWED_TABLES}")


def _authorizer(action: int, arg1, arg2, db_name, trigger) -> int:
    """SQLite authorizer: allow SELECT, reads of whitelisted tables, and
    whitelisted functions. Everything else is denied at compile time."""
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if (arg1 or "").lower() in ALLOWED_TABLES else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_OK if (arg2 or "").lower() in ALLOWED_FUNCTIONS else sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_DENY


def run_readonly(db_path: str | Path, sql: str, params: dict[str, Any] | None = None) -> list[sqlite3.Row]:
    """Validate, then execute on a read-only connection guarded by the authorizer."""
    validate_sql(sql)
    conn = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        conn.set_authorizer(_authorizer)
        return conn.execute(sql, params or {}).fetchall()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Query rejected: {exc}") from exc
    finally:
        conn.close()


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

        rows = run_readonly(self.db_path, sql, params)

        rows_as_dicts = [dict(r) for r in rows]
        summary = "; ".join(
            ", ".join(f"{k}={v}" for k, v in row.items()) for row in rows_as_dicts
        ) or "No rows matched."
        return AgentResult(
            output=summary,
            metadata={"sql": sql, "params": params, "row_count": len(rows_as_dicts), "rows": rows_as_dicts},
        )
