"""Persist user claim verdicts (SQLite)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from src.models.judgment import ClaimReview, TurnReview, UserClaimVerdict

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "judgments.db"


class JudgmentStore:
    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS claim_reviews (
                    session_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    note TEXT DEFAULT '',
                    stakes TEXT DEFAULT 'medium',
                    query TEXT DEFAULT '',
                    reviewed_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_id, claim_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turn_signoff (
                    session_id TEXT NOT NULL,
                    turn_id TEXT NOT NULL,
                    signed_off INTEGER DEFAULT 0,
                    signoff_statement TEXT DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_id)
                )
                """
            )
            conn.commit()

    def upsert_claim_review(
        self,
        session_id: str,
        turn_id: str,
        claim_id: str,
        verdict: UserClaimVerdict,
        note: str = "",
        stakes: str = "medium",
        query: str = "",
    ) -> ClaimReview:
        reviewed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO claim_reviews
                (session_id, turn_id, claim_id, verdict, note, stakes, query, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, turn_id, claim_id) DO UPDATE SET
                    verdict=excluded.verdict,
                    note=excluded.note,
                    reviewed_at=excluded.reviewed_at
                """,
                (
                    session_id,
                    turn_id,
                    claim_id,
                    verdict.value,
                    note or "",
                    stakes,
                    query,
                    reviewed_at,
                ),
            )
            conn.commit()
        return ClaimReview(claim_id=claim_id, verdict=verdict, note=note or "", reviewed_at=reviewed_at)

    def get_turn_reviews(self, session_id: str, turn_id: str) -> TurnReview:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT claim_id, verdict, note, reviewed_at, stakes, query
                FROM claim_reviews
                WHERE session_id = ? AND turn_id = ?
                """,
                (session_id, turn_id),
            ).fetchall()
            sign = conn.execute(
                """
                SELECT signed_off, signoff_statement FROM turn_signoff
                WHERE session_id = ? AND turn_id = ?
                """,
                (session_id, turn_id),
            ).fetchone()

        reviews = [
            ClaimReview(
                claim_id=r["claim_id"],
                verdict=UserClaimVerdict(r["verdict"]),
                note=r["note"] or "",
                reviewed_at=r["reviewed_at"],
            )
            for r in rows
        ]
        query = rows[0]["query"] if rows else ""
        stakes = rows[0]["stakes"] if rows else "medium"
        return TurnReview(
            session_id=session_id,
            turn_id=turn_id,
            query=query,
            stakes=stakes,
            claim_reviews=reviews,
            export_signed_off=bool(sign["signed_off"]) if sign else False,
            signoff_statement=sign["signoff_statement"] if sign else "",
        )

    def set_signoff(
        self,
        session_id: str,
        turn_id: str,
        signed_off: bool,
        statement: str = "",
    ) -> None:
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO turn_signoff (session_id, turn_id, signed_off, signoff_statement, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, turn_id) DO UPDATE SET
                    signed_off=excluded.signed_off,
                    signoff_statement=excluded.signoff_statement,
                    updated_at=excluded.updated_at
                """,
                (session_id, turn_id, int(signed_off), statement, updated_at),
            )
            conn.commit()

    def list_rejected_for_session(self, session_id: str) -> List[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT turn_id, claim_id, note, query, reviewed_at
                FROM claim_reviews
                WHERE session_id = ? AND verdict = 'reject'
                ORDER BY reviewed_at DESC
                """,
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]


@lru_cache
def get_judgment_store() -> JudgmentStore:
    return JudgmentStore()
