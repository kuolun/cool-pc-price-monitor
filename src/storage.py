"""SQLite storage for runs + snapshots."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from src.models import MatchResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  fetched_option_count INTEGER,
  error TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  rule_key TEXT NOT NULL,
  match_mode TEXT NOT NULL,
  price INTEGER,
  option_value TEXT,
  option_text TEXT,
  UNIQUE(run_id, rule_key)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_rule_price
  ON snapshots(rule_key, price);
"""


class Storage:
    def __init__(self, path: str | Path) -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def record_run_start(self, started_at: datetime) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (started_at, status) VALUES (?, 'running')",
            (started_at.isoformat(),),
        )
        self.conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def record_run_end(
        self,
        run_id: int,
        ended_at: datetime,
        status: str,
        fetched_option_count: int | None = None,
        error: str | None = None,
    ) -> None:
        self.conn.execute(
            "UPDATE runs SET ended_at=?, status=?, fetched_option_count=?, error=? WHERE id=?",
            (ended_at.isoformat(), status, fetched_option_count, error, run_id),
        )
        self.conn.commit()

    def record_snapshots(self, run_id: int, matches: list[MatchResult]) -> None:
        rows = []
        for m in matches:
            if m.raw is None:
                rows.append((run_id, m.rule.key, m.mode, None, None, None))
            else:
                rows.append(
                    (
                        run_id,
                        m.rule.key,
                        m.mode,
                        m.raw.price,
                        m.raw.option_value,
                        m.raw.option_text,
                    )
                )
        self.conn.executemany(
            "INSERT INTO snapshots "
            "(run_id, rule_key, match_mode, price, option_value, option_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        self.conn.commit()

    def query_last_price_before(
        self,
        rule_key: str,
        before: datetime,
    ) -> int | None:
        cur = self.conn.execute(
            "SELECT s.price FROM snapshots s JOIN runs r ON s.run_id = r.id "
            "WHERE s.rule_key=? AND r.started_at < ? AND s.price IS NOT NULL "
            "ORDER BY r.started_at DESC LIMIT 1",
            (rule_key, before.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def query_low(
        self,
        rule_key: str,
        start: datetime,
        end: datetime,
    ) -> int | None:
        cur = self.conn.execute(
            "SELECT MIN(s.price) FROM snapshots s JOIN runs r ON s.run_id = r.id "
            "WHERE s.rule_key=? AND r.started_at BETWEEN ? AND ? "
            "AND s.price IS NOT NULL",
            (rule_key, start.isoformat(), end.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    def query_high(
        self,
        rule_key: str,
        start: datetime,
        end: datetime,
    ) -> int | None:
        cur = self.conn.execute(
            "SELECT MAX(s.price) FROM snapshots s JOIN runs r ON s.run_id = r.id "
            "WHERE s.rule_key=? AND r.started_at BETWEEN ? AND ? "
            "AND s.price IS NOT NULL",
            (rule_key, start.isoformat(), end.isoformat()),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None

    def query_total_history(
        self,
        quantities: dict[str, int],
        start: datetime,
        end: datetime,
    ) -> list[tuple[str, int]]:
        """Return [(date_iso, total_price)] per day in [start, end].

        Sums `price * quantity` across all rules in `quantities` using the
        latest run on each day. Days missing any rule's price are skipped.
        """
        if not quantities:
            return []
        placeholders = ",".join("?" * len(quantities))
        rule_keys = list(quantities.keys())
        cur = self.conn.execute(
            f"""
            WITH daily_runs AS (
              SELECT DATE(r.started_at) AS day, MAX(r.started_at) AS latest_at
              FROM runs r
              WHERE r.started_at BETWEEN ? AND ? AND r.status IN ('ok', 'partial')
              GROUP BY DATE(r.started_at)
            )
            SELECT d.day, s.rule_key, s.price
            FROM daily_runs d
            JOIN runs r ON r.started_at = d.latest_at
            JOIN snapshots s ON s.run_id = r.id
            WHERE s.rule_key IN ({placeholders})
            ORDER BY d.day, s.rule_key
            """,
            (start.isoformat(), end.isoformat(), *rule_keys),
        )
        by_day: dict[str, dict[str, int | None]] = {}
        for day, rule_key, price in cur.fetchall():
            by_day.setdefault(day, {})[rule_key] = price

        out: list[tuple[str, int]] = []
        for day, prices in sorted(by_day.items()):
            if any(prices.get(k) is None for k in rule_keys):
                continue
            total = sum(prices[k] * quantities[k] for k in rule_keys)
            out.append((day, total))
        return out

    def close(self) -> None:
        self.conn.close()
