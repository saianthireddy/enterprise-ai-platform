"""Seeds data/demo.db with the SQL Agent's demo schema (employees, tickets, orders).
Run once before starting the API, or let `main.py` auto-seed on first boot.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "demo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    department TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
"""

EMPLOYEES = [
    (1, "Priya Nair", "Sales"),
    (2, "Marcus Webb", "Sales"),
    (3, "Lena Ortiz", "Support"),
    (4, "Jordan Kim", "Engineering"),
]

TICKETS = [
    (1, "Login fails after SSO redirect", "open", "high"),
    (2, "Export button missing on reports page", "open", "medium"),
    (3, "Billing address update request", "closed", "low"),
    (4, "API rate limit too aggressive", "open", "high"),
    (5, "Typo in invoice PDF", "closed", "low"),
]

ORDERS = [
    (1, 1, 42000.0),
    (2, 1, 18500.0),
    (3, 2, 31000.0),
    (4, 2, 9800.0),
]


def seed(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT OR IGNORE INTO employees VALUES (?, ?, ?)", EMPLOYEES)
        conn.executemany("INSERT OR IGNORE INTO tickets VALUES (?, ?, ?, ?)", TICKETS)
        conn.executemany("INSERT OR IGNORE INTO orders VALUES (?, ?, ?)", ORDERS)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded demo database at {DB_PATH}")
