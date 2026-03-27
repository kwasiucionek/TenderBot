# storage.py
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# =========================
# MODELE DANYCH
# =========================


@dataclass
class FilterProfile:
    name: str
    enabled: bool
    order_type: str
    cpv_prefixes: List[str]
    provinces: List[str]


# =========================
# STORAGE
# =========================


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =========================
    # SCHEMA
    # =========================

    def _init_db(self) -> None:
        conn = self._conn()
        cur = conn.cursor()

        # ---- profile filtrów ----
        cur.execute("""
        CREATE TABLE IF NOT EXISTS filter_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            enabled INTEGER NOT NULL,
            order_type TEXT NOT NULL,
            cpv_prefixes TEXT NOT NULL,
            provinces TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # ---- stan ogłoszeń ----
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notice_state (
            object_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """)

        # ---- ogłoszenia ----
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            object_id TEXT PRIMARY KEY,
            profile_name TEXT NOT NULL,
            publication_date TEXT,
            notice_number TEXT,
            bzp_number TEXT,
            submitting_offers_date TEXT,
            cpv_code TEXT,
            organization_name TEXT,
            organization_city TEXT,
            organization_province TEXT,
            order_object TEXT,
            notice_type TEXT,
            tender_type TEXT,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # ---- streszczenia AI ----
        cur.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            object_id TEXT PRIMARY KEY,
            profile_name TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            model_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    # =========================
    # PROFILE
    # =========================

    def load_active_profiles(self) -> List[FilterProfile]:
        conn = self._conn()
        rows = conn.execute("""
            SELECT name, enabled, order_type, cpv_prefixes, provinces
            FROM filter_profiles
            WHERE enabled = 1
        """).fetchall()
        conn.close()

        profiles: List[FilterProfile] = []
        for r in rows:
            profiles.append(
                FilterProfile(
                    name=r["name"],
                    enabled=bool(r["enabled"]),
                    order_type=r["order_type"],
                    cpv_prefixes=json.loads(r["cpv_prefixes"]),
                    provinces=json.loads(r["provinces"]),
                )
            )
        return profiles

    # =========================
    # FINGERPRINT
    # =========================

    @staticmethod
    def fingerprint_notice(notice: Dict[str, Any]) -> str:
        keys = [
            "objectId",
            "noticeType",
            "noticeNumber",
            "bzpNumber",
            "publicationDate",
            "orderObject",
            "cpvCode",
            "submittingOffersDate",
            "organizationName",
            "organizationCity",
            "organizationProvince",
            "tenderType",
        ]
        reduced = {k: notice.get(k) for k in keys}
        blob = json.dumps(reduced, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def get_state_fingerprint(self, object_id: str) -> Optional[str]:
        conn = self._conn()
        row = conn.execute(
            "SELECT fingerprint FROM notice_state WHERE object_id=?", (object_id,)
        ).fetchone()
        conn.close()
        return row["fingerprint"] if row else None

    # =========================
    # UPSERT NOTICE
    # =========================

    def upsert_notice_and_state(
        self,
        profile_name: str,
        notice: Dict[str, Any],
        fingerprint: str,
        now_iso: str,
    ) -> None:
        object_id = notice.get("objectId")
        if not object_id:
            return

        payload_json = json.dumps(notice, ensure_ascii=False)

        conn = self._conn()
        cur = conn.cursor()

        cur.execute(
            """
        INSERT INTO notices(
            object_id, profile_name, publication_date, notice_number, bzp_number,
            submitting_offers_date, cpv_code, organization_name, organization_city,
            organization_province, order_object, notice_type, tender_type,
            payload_json, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(object_id) DO UPDATE SET
            profile_name=excluded.profile_name,
            publication_date=excluded.publication_date,
            notice_number=excluded.notice_number,
            bzp_number=excluded.bzp_number,
            submitting_offers_date=excluded.submitting_offers_date,
            cpv_code=excluded.cpv_code,
            organization_name=excluded.organization_name,
            organization_city=excluded.organization_city,
            organization_province=excluded.organization_province,
            order_object=excluded.order_object,
            notice_type=excluded.notice_type,
            tender_type=excluded.tender_type,
            payload_json=excluded.payload_json,
            updated_at=excluded.updated_at
        """,
            (
                object_id,
                profile_name,
                notice.get("publicationDate"),
                notice.get("noticeNumber"),
                notice.get("bzpNumber"),
                notice.get("submittingOffersDate"),
                notice.get("cpvCode"),
                notice.get("organizationName"),
                notice.get("organizationCity"),
                notice.get("organizationProvince"),
                notice.get("orderObject"),
                notice.get("noticeType"),
                notice.get("tenderType"),
                payload_json,
                now_iso,
            ),
        )

        cur.execute(
            """
        INSERT INTO notice_state(object_id, fingerprint, last_seen_at)
        VALUES(?,?,?)
        ON CONFLICT(object_id) DO UPDATE SET
            fingerprint=excluded.fingerprint,
            last_seen_at=excluded.last_seen_at
        """,
            (
                object_id,
                fingerprint,
                now_iso,
            ),
        )

        conn.commit()
        conn.close()

    # =========================
    # SUMMARY
    # =========================

    def get_notices_needing_summary(self, limit: int = 50):
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT n.*
            FROM notices n
            LEFT JOIN summaries s ON s.object_id = n.object_id
            WHERE s.object_id IS NULL
               OR n.updated_at > s.updated_at
               OR s.summary_json = '{}'
            ORDER BY n.updated_at DESC
            LIMIT ?
        """,
            (limit,),
        ).fetchall()
        conn.close()
        return rows

    def upsert_summary(
        self, object_id: str, profile_name: str, summary: dict, model_name: str
    ):
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO summaries(object_id, profile_name, summary_json, model_name, created_at, updated_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(object_id) DO UPDATE SET
                profile_name=excluded.profile_name,
                summary_json=excluded.summary_json,
                model_name=excluded.model_name,
                updated_at=excluded.updated_at
        """,
            (
                object_id,
                profile_name,
                json.dumps(summary, ensure_ascii=False),
                model_name,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
