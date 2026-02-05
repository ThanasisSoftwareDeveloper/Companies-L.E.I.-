from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class CachedLei:
    entity_status: Optional[str]
    next_renewal_date: Optional[str]
    source: Optional[str]
    fetched_at: str


class LeiCache:
    def __init__(self, db_path: str) -> None:
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lei_cache (
              lei TEXT PRIMARY KEY,
              entity_status TEXT,
              next_renewal_date TEXT,
              source TEXT,
              fetched_at TEXT
            )
            """
        )
        self.conn.commit()

    def get(self, lei: str, max_age_days: int) -> Optional[CachedLei]:
        row = self.conn.execute(
            "SELECT entity_status, next_renewal_date, source, fetched_at FROM lei_cache WHERE lei=?",
            (lei,),
        ).fetchone()
        if not row:
            return None
        entity_status, next_renewal_date, source, fetched_at = row
        try:
            fetched_dt = datetime.fromisoformat(fetched_at)
        except Exception:
            return None

        if datetime.utcnow() - fetched_dt > timedelta(days=max_age_days):
            return None

        return CachedLei(entity_status, next_renewal_date, source, fetched_at)

    def put(self, lei: str, entity_status: str | None, next_renewal_date: str | None, source: str) -> None:
        self.conn.execute(
            """
            INSERT INTO lei_cache(lei, entity_status, next_renewal_date, source, fetched_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(lei) DO UPDATE SET
              entity_status=excluded.entity_status,
              next_renewal_date=excluded.next_renewal_date,
              source=excluded.source,
              fetched_at=excluded.fetched_at
            """,
            (lei, entity_status, next_renewal_date, source, datetime.utcnow().isoformat()),
        )
        self.conn.commit()