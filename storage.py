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
        self._migrate_db()

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
        # UWAGA: notice_state jest pamięcią monitora — NIE usuwać razem z notices!
        # Bez tych wpisów monitor ponownie pobierze te same ogłoszenia.
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notice_state (
            object_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            updated_at TEXT
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
            updated_at TEXT NOT NULL,
            user_status TEXT,
            tender_id TEXT,
            is_below_eu INTEGER
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
            updated_at TEXT NOT NULL,
            detailed_text TEXT
        )
        """)

        # ---- ignorowane kody CPV ----
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ignored_cpv (
            cpv_code TEXT PRIMARY KEY,
            description TEXT,
            ignored_at TEXT NOT NULL
        )
        """)

        conn.commit()
        conn.close()

    def _migrate_db(self) -> None:
        """Dodaje brakujące kolumny do istniejących baz (migracja)."""
        conn = self._conn()
        cur = conn.cursor()

        # Pobierz istniejące kolumny
        def columns(table: str) -> set:
            return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}

        notices_cols = columns("notices")
        if "user_status" not in notices_cols:
            cur.execute("ALTER TABLE notices ADD COLUMN user_status TEXT")
        if "tender_id" not in notices_cols:
            cur.execute("ALTER TABLE notices ADD COLUMN tender_id TEXT")
        if "is_below_eu" not in notices_cols:
            cur.execute("ALTER TABLE notices ADD COLUMN is_below_eu INTEGER")

        state_cols = columns("notice_state")
        if "updated_at" not in state_cols:
            cur.execute("ALTER TABLE notice_state ADD COLUMN updated_at TEXT")

        summaries_cols = columns("summaries")
        if "detailed_text" not in summaries_cols:
            cur.execute("ALTER TABLE summaries ADD COLUMN detailed_text TEXT")

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
    # IGNORED CPV
    # =========================

    def load_ignored_cpv_codes(self) -> set[str]:
        """Załaduj zestaw ignorowanych kodów CPV."""
        conn = self._conn()
        rows = conn.execute("SELECT cpv_code FROM ignored_cpv").fetchall()
        conn.close()
        return {r["cpv_code"] for r in rows}

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

        is_below_eu = notice.get("isTenderAmountBelowEU")
        if is_below_eu is True:
            is_below_eu_int = 1
        elif is_below_eu is False:
            is_below_eu_int = 0
        else:
            is_below_eu_int = None

        # user_status z notice (np. ustawiony przez should_auto_dismiss)
        new_status = notice.get("user_status")

        conn = self._conn()
        cur = conn.cursor()

        cur.execute(
            """
        INSERT INTO notices(
            object_id, profile_name, publication_date, notice_number, bzp_number,
            submitting_offers_date, cpv_code, organization_name, organization_city,
            organization_province, order_object, notice_type, tender_type,
            payload_json, updated_at, tender_id, is_below_eu, user_status
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            updated_at=excluded.updated_at,
            tender_id=excluded.tender_id,
            is_below_eu=excluded.is_below_eu,
            user_status=CASE
                WHEN excluded.user_status = 'dismissed' THEN 'dismissed'
                ELSE notices.user_status
            END
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
                notice.get("tenderType") or notice.get("orderType"),
                payload_json,
                now_iso,
                notice.get("tenderId"),
                is_below_eu_int,
                new_status,
            ),
        )

        cur.execute(
            """
        INSERT INTO notice_state(object_id, fingerprint, last_seen_at, updated_at)
        VALUES(?,?,?,?)
        ON CONFLICT(object_id) DO UPDATE SET
            fingerprint=excluded.fingerprint,
            last_seen_at=excluded.last_seen_at,
            updated_at=excluded.updated_at
        """,
            (object_id, fingerprint, now_iso, now_iso),
        )

        conn.commit()
        conn.close()

    # =========================
    # USUWANIE
    # =========================

    def delete_dismissed(self) -> int:
        """
        Usuwa odrzucone ogłoszenia (user_status = 'dismissed') i ich streszczenia.

        WAŻNE: celowo NIE usuwa notice_state — bez tych wpisów monitor
        ponownie pobrałby te same ogłoszenia przy następnym uruchomieniu.

        Zwraca liczbę usuniętych ogłoszeń.
        """
        conn = self._conn()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM summaries
            WHERE object_id IN (
                SELECT object_id FROM notices WHERE user_status = 'dismissed'
            )
        """)

        cur.execute("DELETE FROM notices WHERE user_status = 'dismissed'")
        deleted = cur.rowcount

        conn.commit()

        # VACUUM poza transakcją
        conn.execute("VACUUM")
        conn.close()

        return deleted

    def delete_notice(self, object_id: str) -> None:
        """
        Trwałe usunięcie pojedynczego ogłoszenia (przycisk 🗑️ w UI).

        Usuwa z notices i summaries, ale zostawia notice_state
        żeby monitor nie pobierał go ponownie.
        """
        conn = self._conn()
        conn.execute("DELETE FROM summaries WHERE object_id = ?", (object_id,))
        conn.execute("DELETE FROM notices WHERE object_id = ?", (object_id,))
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
            WHERE (n.user_status IS NULL OR n.user_status != 'dismissed')
              AND (
                s.object_id IS NULL
                OR n.updated_at > s.updated_at
                OR s.summary_json = '{}'
                OR s.detailed_text IS NULL
                OR s.detailed_text = ''
              )
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
