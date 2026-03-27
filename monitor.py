# monitor.py
"""
TenderBot monitor — pobiera ogłoszenia z dwóch źródeł:
  1. Board/Search (ezamowienia.gov.pl) — ogłoszenia krajowe + część unijnych
  2. TED Search API (api.ted.europa.eu) — ogłoszenia unijne (kompletniejsze)

Board/Search NIE indeksuje wszystkich ogłoszeń eForms/TED, dlatego
TED API jest potrzebne jako uzupełnienie.

Zmienne środowiskowe:
  TENDERBOT_DB          — ścieżka do bazy SQLite (domyślnie: data/tenderbot.sqlite)
  TENDERBOT_HOURS_BACK  — ile godzin wstecz szukać (domyślnie: 168 = 7 dni)
  TENDERBOT_PAGE_SIZE   — rozmiar strony (domyślnie: 100)
  TENDERBOT_ONLY_OPEN   — 1 = tylko wszczęte
  TENDERBOT_SKIP_TED    — 1 = pomiń źródło TED
  TENDERBOT_DEBUG       — 1 = verbose logging
  TENDERBOT_TARGET_ID   — szukaj konkretnego objectId (debug)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx
from bzp_client import BzpQuery, iter_notices
from ted_client import (
    ORDER_TYPE_TO_CONTRACT_NATURE,
    TedQuery,
    build_expert_query,
    iter_ted_notices,
    normalize_ted_notice,
    provinces_to_nuts,
)

# -------------------------
# Time helpers
# -------------------------


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


# -------------------------
# CPV parsing
# -------------------------

_CPV_RE = re.compile(r"(\d{8})(?:-\d)?")


def cpv_codes8(cpv_field: str) -> List[str]:
    """Wyciąga 8-cyfrowe kody CPV z pola cpvCode."""
    if not cpv_field:
        return []
    return _CPV_RE.findall(cpv_field)


def matches_cpv(cpv_field: str, cpv_prefixes: List[str]) -> bool:
    """
    Sprawdza czy pole CPV pasuje do któregoś z prefixów profilu.

    W hierarchii CPV końcowe zera to wildcardy:
      72000000 = cała grupa 72*
      72250000 = podgrupa 7225*
      72253200 = konkretny kod
    """
    codes = cpv_codes8(cpv_field)

    for wanted in cpv_prefixes:
        wanted_clean = re.sub(r"\D", "", wanted).strip()
        if not wanted_clean:
            continue

        # Obcinamy trailing zera — to wildcardy w hierarchii CPV
        wanted_prefix = wanted_clean.rstrip("0") or wanted_clean[:1]

        if codes:
            if any(code.startswith(wanted_prefix) for code in codes):
                return True
        else:
            digits = re.sub(r"\D", "", cpv_field)
            if digits.startswith(wanted_prefix):
                return True
    return False


def matches_province(
    notice: Dict[str, Any],
    provinces: List[str],
) -> bool:
    """
    Sprawdza czy ogłoszenie pasuje do wybranych województw.
    Pusta lista = wszystkie województwa (brak filtra).
    """
    if not provinces:
        return True
    prov = (notice.get("organizationProvince") or "").strip()
    if not prov:
        # Ogłoszenie bez województwa (np. TED) — przepuść
        return True
    return prov in provinces


def matches_profile(
    notice: Dict[str, Any],
    cpv_prefixes: List[str],
) -> bool:
    """
    Filtruje ogłoszenie po CPV.

    Ogłoszenie bez CPV jest przepuszczane (lepiej za dużo niż za mało).
    """
    cpv_field = (notice.get("cpvCode") or "").strip()
    if not cpv_field:
        # Ogłoszenie bez CPV — przepuść (lepiej za dużo niż za mało)
        return True
    return matches_cpv(cpv_field, cpv_prefixes)


# -------------------------
# DB schema + migrations
# -------------------------


def ensure_parent_dir(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in cols}


def init_db(db_path: str) -> None:
    ensure_parent_dir(db_path)
    conn = connect(db_path)
    cur = conn.cursor()

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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS notice_state (
        object_id TEXT PRIMARY KEY,
        fingerprint TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
    )
    """)

    # Migracje
    ncols = table_columns(conn, "notices")
    if "tender_id" not in ncols:
        cur.execute("ALTER TABLE notices ADD COLUMN tender_id TEXT")
    if "is_below_eu" not in ncols:
        cur.execute("ALTER TABLE notices ADD COLUMN is_below_eu INTEGER")

    scols = table_columns(conn, "notice_state")
    if "updated_at" not in scols:
        cur.execute("ALTER TABLE notice_state ADD COLUMN updated_at TEXT")

    # Migracja: countries w profilach
    pcols = table_columns(conn, "filter_profiles")
    if "countries" not in pcols:
        cur.execute(
            "ALTER TABLE filter_profiles ADD COLUMN countries TEXT"
            " NOT NULL DEFAULT '[\"POL\"]'"
        )

    # Migracja: user_status w notices (starred / dismissed / NULL)
    if "user_status" not in ncols:
        cur.execute("ALTER TABLE notices ADD COLUMN user_status TEXT")

    # Fix: TED notices zawsze EU (is_below_eu=0)
    cur.execute("""
        UPDATE notices SET is_below_eu = 0
        WHERE object_id LIKE 'ted-%' AND is_below_eu IS NULL
    """)
    # Fix: BZP notices bez is_below_eu → domyślnie krajowe (1)
    cur.execute("""
        UPDATE notices SET is_below_eu = 1
        WHERE object_id NOT LIKE 'ted-%' AND is_below_eu IS NULL
    """)

    cur.execute(
        """
        UPDATE notice_state
        SET last_seen_at = COALESCE(last_seen_at, updated_at, ?)
        WHERE last_seen_at IS NULL
    """,
        (utc_now().isoformat(),),
    )

    conn.commit()
    conn.close()


# -------------------------
# Profiles
# -------------------------


@dataclass
class Profile:
    name: str
    enabled: bool
    order_types: List[str]  # ["Services", "Supplies", "Works"] — puste = wszystkie
    cpv_prefixes: List[str]
    provinces: List[str]
    countries: List[str]  # kody ISO3 dla TED (np. POL, DEU, CZE)


def load_active_profiles(db_path: str) -> List[Profile]:
    conn = connect(db_path)
    rows = conn.execute("""
        SELECT name, enabled, order_type, cpv_prefixes, provinces,
               countries
        FROM filter_profiles
        WHERE enabled = 1
        ORDER BY name
    """).fetchall()
    conn.close()

    out: List[Profile] = []
    for r in rows:
        raw_countries = r["countries"]
        try:
            countries = json.loads(raw_countries) if raw_countries else ["POL"]
        except (json.JSONDecodeError, TypeError):
            countries = ["POL"]

        # order_type: backward compat — stary string → lista
        raw_ot = r["order_type"] or ""
        try:
            order_types = json.loads(raw_ot)
            if isinstance(order_types, str):
                order_types = [order_types] if order_types else []
        except (json.JSONDecodeError, TypeError):
            order_types = [raw_ot] if raw_ot else []

        out.append(
            Profile(
                name=r["name"],
                enabled=bool(r["enabled"]),
                order_types=order_types,
                cpv_prefixes=json.loads(r["cpv_prefixes"]),
                provinces=json.loads(r["provinces"]),
                countries=countries,
            )
        )
    return out


# -------------------------
# Fingerprint + upsert
# -------------------------


def fingerprint_notice(notice: Dict[str, Any]) -> str:
    payload = {
        "objectId": notice.get("objectId"),
        "noticeNumber": notice.get("noticeNumber"),
        "bzpNumber": notice.get("bzpNumber"),
        "publicationDate": notice.get("publicationDate"),
        "submittingOffersDate": notice.get("submittingOffersDate"),
        "cpvCode": notice.get("cpvCode"),
        "orderObject": notice.get("orderObject"),
        "organizationName": notice.get("organizationName"),
        "organizationProvince": notice.get("organizationProvince"),
        "tenderId": notice.get("tenderId"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_state_fingerprint(db_path: str, object_id: str) -> Optional[str]:
    conn = connect(db_path)
    row = conn.execute(
        "SELECT fingerprint FROM notice_state WHERE object_id = ?",
        (object_id,),
    ).fetchone()
    conn.close()
    return row["fingerprint"] if row else None


def load_dismissed_ids(db_path: str) -> set[str]:
    """Załaduj object_id ogłoszeń oznaczonych jako dismissed (❌)."""
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT object_id FROM notices WHERE user_status = 'dismissed'"
    ).fetchall()
    conn.close()
    return {r["object_id"] for r in rows}


def upsert_notice_and_state(
    db_path: str,
    profile_name: str,
    notice: Dict[str, Any],
    fp: str,
    now_iso: str,
) -> None:
    conn = connect(db_path)
    cur = conn.cursor()

    object_id = notice.get("objectId") or notice.get("object_id")
    if not object_id:
        conn.close()
        return

    payload_json = json.dumps(notice, ensure_ascii=False, default=str)
    tender_id = notice.get("tenderId")
    is_below_eu = notice.get("isTenderAmountBelowEU")
    if is_below_eu is True:
        is_below_eu_int = 1
    elif is_below_eu is False:
        is_below_eu_int = 0
    else:
        is_below_eu_int = None

    cur.execute(
        """
        INSERT INTO notices(
            object_id, profile_name, publication_date, notice_number, bzp_number,
            submitting_offers_date, cpv_code, organization_name, organization_city,
            organization_province, order_object, notice_type, tender_type,
            payload_json, updated_at, tender_id, is_below_eu
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            is_below_eu=excluded.is_below_eu
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
            tender_id,
            is_below_eu_int,
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
        (object_id, fp, now_iso, now_iso),
    )

    conn.commit()
    conn.close()


# -------------------------
# HTTP retry wrapper
# -------------------------


def iter_notices_with_retry(
    client: httpx.Client, q: BzpQuery, max_retries: int = 6
) -> Iterable[Dict[str, Any]]:
    attempt = 0
    backoff = 1.0
    while True:
        try:
            yield from iter_notices(client, q)
            return
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response else None
            if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                attempt += 1
                print(f"  [RETRY] HTTP {status}, attempt {attempt}, sleep {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
                continue
            raise


# -------------------------
# CPV: klasyfikacja kodów do API
# -------------------------

# Próg: kod z ≥3 końcowymi zerami to kod grupowy w hierarchii CPV.
# API Board/Search robi EXACT match, więc 34923000 nie znajdzie 34923100.
# Kody grupowe → query BEZ CpvCode, filtr lokalny.
# Kody z ≤2 zerami (np. 35125300, 72253200) → exact match w API.
_BROAD_TRAILING_ZEROS = 3


def classify_cpv_codes(
    cpv_prefixes: List[str],
) -> tuple[bool, List[str]]:
    """
    Dzieli kody CPV na:
      - has_broad: True jeśli są kody grupowe (≥3 trailing zeros)
        → wymagają query BEZ CpvCode, filtr lokalny
      - exact_codes: lista konkretnych kodów (≤2 trailing zeros)
        → query z CpvCode=exact

    Kody exact pokryte przez broad są pomijane.
    """
    broad_prefixes: List[str] = []
    exact_codes: List[str] = []

    for cpv in cpv_prefixes:
        d = re.sub(r"\D", "", cpv).strip()
        if not d:
            continue
        significant = d.rstrip("0") or d[:1]
        trailing_zeros = len(d) - len(significant)

        if trailing_zeros >= _BROAD_TRAILING_ZEROS:
            broad_prefixes.append(significant)
        else:
            exact_codes.append(d)

    # Usuń exact kody pokryte przez broad
    # np. jeśli broad ma "72" (z 72000000), to 72253200 jest zbędne
    if broad_prefixes:
        filtered_exact = []
        for ex in exact_codes:
            covered = any(ex.startswith(bp) for bp in broad_prefixes)
            if not covered:
                filtered_exact.append(ex)
        exact_codes = filtered_exact

    # Deduplikacja exact
    seen = set()
    deduped = []
    for ex in exact_codes:
        if ex not in seen:
            seen.add(ex)
            deduped.append(ex)
    exact_codes = deduped

    has_broad = len(broad_prefixes) > 0
    return has_broad, exact_codes


# -------------------------
# Budowanie listy zapytań
# -------------------------


def build_queries_for_profile(
    profile: Profile,
    date_from: datetime,
    date_to: datetime,
    page_size: int,
) -> List[BzpQuery]:
    """
    Buduje listę zapytań API dla profilu.

    API Board/Search robi EXACT MATCH na CpvCode (nie prefix!).
    Dlatego:
      - Kody grupowe (72000000, 48000000...) → query BEZ CpvCode,
        filtrujemy CPV lokalnie w matches_profile()
      - Kody konkretne (35125300...) → query Z CpvCode=exact

    Każdy typ ma 2 przejścia:
      1. Krajowe: + Province + IsTenderAmountBelowEU=true
      2. Unijne:  + IsTenderAmountBelowEU=false (bez province)
    """
    has_broad, exact_codes = classify_cpv_codes(profile.cpv_prefixes)
    provinces = profile.provinces or []
    queries: List[BzpQuery] = []

    def _add_pl_eu_pair(cpv_code: Optional[str], order_type: Optional[str]) -> None:
        """Dodaje parę zapytań (krajowe + unijne) dla danego CpvCode i OrderType."""
        # Przejście 1: KRAJOWE
        if provinces:
            for prov in provinces:
                queries.append(
                    BzpQuery(
                        publication_from=date_from,
                        publication_to=date_to,
                        page_size=page_size,
                        order_type=order_type,
                        cpv_code=cpv_code,
                        organization_province=prov,
                        is_below_eu=True,
                    )
                )
        else:
            queries.append(
                BzpQuery(
                    publication_from=date_from,
                    publication_to=date_to,
                    page_size=page_size,
                    order_type=order_type,
                    cpv_code=cpv_code,
                    is_below_eu=True,
                )
            )

        # Przejście 2: UNIJNE (bez province)
        queries.append(
            BzpQuery(
                publication_from=date_from,
                publication_to=date_to,
                page_size=page_size,
                order_type=order_type,
                cpv_code=cpv_code,
                is_below_eu=False,
            )
        )

    # Lista typów zamówienia — puste = jedno zapytanie bez filtra
    ot_list = profile.order_types if profile.order_types else [None]

    # Kody grupowe → zapytanie bez CpvCode (filtr CPV lokalny)
    if has_broad:
        for ot in ot_list:
            _add_pl_eu_pair(cpv_code=None, order_type=ot)

    # Kody konkretne → zapytanie z exact CpvCode
    for cpv in exact_codes:
        for ot in ot_list:
            _add_pl_eu_pair(cpv_code=cpv, order_type=ot)

    return queries


# -------------------------
# Main
# -------------------------


def main() -> None:
    db_path = os.getenv("TENDERBOT_DB", "data/tenderbot.sqlite")
    init_db(db_path)

    hours_back = int(os.getenv("TENDERBOT_HOURS_BACK", "168"))
    page_size = int(os.getenv("TENDERBOT_PAGE_SIZE", "100"))
    only_open = os.getenv("TENDERBOT_ONLY_OPEN", "0") == "1"
    skip_ted = os.getenv("TENDERBOT_SKIP_TED", "0") == "1"
    debug = os.getenv("TENDERBOT_DEBUG", "0") == "1"
    target_id = os.getenv("TENDERBOT_TARGET_ID", "").strip()

    profiles = load_active_profiles(db_path)
    if not profiles:
        print("No active profiles. (Enable one in Streamlit panel.)")
        return

    now = utc_now()
    date_from = now - timedelta(hours=hours_back)
    date_to = now

    print(f"Zakres: {date_from.isoformat()} → {date_to.isoformat()} ({hours_back}h)")

    headers = {"User-Agent": "TenderBot/2.0"}

    total_new = 0
    total_changed = 0
    total_seen = 0
    total_matched = 0
    total_skipped_cpv = 0
    total_skipped_prov = 0
    seen_ids: set[str] = set()

    # Pomijaj ogłoszenia oznaczone jako dismissed (❌)
    dismissed = load_dismissed_ids(db_path)
    if dismissed:
        seen_ids.update(dismissed)
        print(f"Pomijam {len(dismissed)} dismissed ogłoszeń")

    with httpx.Client(headers=headers, timeout=httpx.Timeout(60.0)) as client:
        for p in profiles:
            print(f"\n{'=' * 60}")
            print(
                f"Profil: {p.name} | CPV: {p.cpv_prefixes} | "
                f"Prov: {p.provinces or 'wszystkie'} | "
                f"Kraje: {p.countries or ['POL']}"
            )
            print(f"{'=' * 60}")

            # =====================
            # ŹRÓDŁO 1: Board/Search (ezamowienia.gov.pl — tylko Polska)
            # =====================
            run_bzp = "POL" in (p.countries or ["POL"])
            if not run_bzp:
                print("  [SKIP] Board/Search — profil nie obejmuje Polski")

            if run_bzp:
                queries = build_queries_for_profile(p, date_from, date_to, page_size)

                has_broad, exact_codes = classify_cpv_codes(p.cpv_prefixes)
                print(
                    f"Board/Search: broad={'TAK' if has_broad else 'NIE'}"
                    f" | exact={exact_codes or '(brak)'}"
                    f" | zapytań: {len(queries)}"
                )

                for qi, q in enumerate(queries):
                    tag = "EU" if q.is_below_eu is False else "PL"

                    if debug:
                        print(
                            f"[QUERY {qi + 1}/{len(queries)}][{tag}] "
                            f"cpv={q.cpv_code or '(brak→lokalny filtr)'} "
                            f"prov={q.organization_province} "
                            f"belowEU={q.is_below_eu}"
                        )

                    query_count = 0

                    for notice in iter_notices_with_retry(client, q):
                        object_id = notice.get("objectId", "")

                        # Deduplikacja
                        if object_id in seen_ids:
                            continue
                        seen_ids.add(object_id)

                        total_seen += 1
                        query_count += 1

                        # Stamp is_below_eu z parametru zapytania
                        # (API nie zwraca tego pola w odpowiedzi)
                        if notice.get("isTenderAmountBelowEU") is None:
                            notice["isTenderAmountBelowEU"] = q.is_below_eu

                        # Debug: target
                        if target_id and object_id == target_id:
                            print(f"\n🎯 TARGET FOUND: {object_id}")
                            for k in [
                                "noticeType",
                                "noticeTypeTed",
                                "orderType",
                                "cpvCode",
                                "organizationProvince",
                                "organizationName",
                                "organizationCountry",
                                "isTenderAmountBelowEU",
                                "orderObject",
                                "submittingOffersDate",
                            ]:
                                print(f"   {k}: {notice.get(k)}")

                        # Filtr: tylko wszczęte (otwarte)
                        if only_open:
                            if notice.get("procedureResult"):
                                continue
                            deadline = parse_dt(notice.get("submittingOffersDate"))
                            if deadline is not None and deadline < now:
                                continue

                        # Lokalna weryfikacja CPV
                        if not matches_profile(notice, p.cpv_prefixes):
                            total_skipped_cpv += 1
                            if debug:
                                print(
                                    f"  [SKIP-CPV] {object_id} "
                                    f"cpv={notice.get('cpvCode', '')[:30]}"
                                )
                            continue

                        # Lokalna weryfikacja województwa
                        if not matches_province(notice, p.provinces):
                            total_skipped_prov += 1
                            if debug:
                                print(
                                    f"  [SKIP-PROV] {object_id} "
                                    f"prov={notice.get('organizationProvince', '')}"
                                )
                            continue

                        total_matched += 1
                        if not object_id:
                            continue

                        fp = fingerprint_notice(notice)
                        prev_fp = get_state_fingerprint(db_path, object_id)
                        now_iso = utc_now().isoformat()

                        print(
                            f"DEBUG tender_type={notice.get('tenderType')!r}  orderType={notice.get('orderType')!r}"
                        )

                        upsert_notice_and_state(
                            db_path,
                            p.name,
                            notice,
                            fp,
                            now_iso,
                        )

                        is_eu = notice.get("isTenderAmountBelowEU") is False
                        eu_tag = "EU" if is_eu else "PL"

                        if prev_fp is None:
                            total_new += 1
                            print(
                                f"[NEW][{eu_tag}] {object_id} | "
                                f"{(notice.get('orderObject') or '')[:80]} | "
                                f"CPV {(notice.get('cpvCode') or '')[:20]} | "
                                f"ORG {(notice.get('organizationName') or '')[:40]}"
                            )
                        elif prev_fp != fp:
                            total_changed += 1
                            print(
                                f"[CHANGED][{eu_tag}] {object_id} | "
                                f"{(notice.get('orderObject') or '')[:80]}"
                            )

                    if debug:
                        print(f"  → {query_count} unique notices")

            # =====================
            # ŹRÓDŁO 2: TED API (ogłoszenia unijne — kompletniejsze)
            # =====================
            if not skip_ted:
                countries = p.countries or ["POL"]
                # NUTS: filtr regionu (tylko PL województwa → NUTS2)
                nuts = provinces_to_nuts(p.provinces) if p.provinces else []
                nuts_info = f" | NUTS: {nuts}" if nuts else ""
                # Typ zamówienia → contract-nature (lista)
                cn_list = [
                    ORDER_TYPE_TO_CONTRACT_NATURE[t]
                    for t in p.order_types
                    if t in ORDER_TYPE_TO_CONTRACT_NATURE
                ]
                cn_info = f" | typ: {','.join(cn_list)}" if cn_list else ""
                print(
                    f"\n--- TED API (unijne) | profil: {p.name} | "
                    f"kraje: {','.join(countries)}{nuts_info}{cn_info} ---"
                )

                ted_q = TedQuery(
                    cpv_codes=p.cpv_prefixes,
                    countries=countries,
                    nuts_codes=nuts,
                    contract_natures=cn_list,
                    publication_from=date_from,
                    publication_to=date_to,
                    notice_types=["cn-standard", "cn-social"],
                    limit=100,
                )

                if debug:
                    print(f"[TED QUERY] {build_expert_query(ted_q)}")

                ted_count = 0
                ted_new = 0
                try:
                    for ted_item in iter_ted_notices(client, ted_q):
                        notice = normalize_ted_notice(ted_item)
                        object_id = notice.get("objectId", "")

                        if object_id in seen_ids:
                            continue
                        seen_ids.add(object_id)

                        total_seen += 1
                        ted_count += 1

                        # Debug: target
                        if target_id and target_id in object_id:
                            print(f"\n🎯 TARGET FOUND (TED): {object_id}")
                            for k in [
                                "noticeType",
                                "cpvCode",
                                "orderObject",
                                "organizationName",
                                "submittingOffersDate",
                            ]:
                                print(f"   {k}: {notice.get(k)}")

                        # Filtr: tylko otwarte
                        if only_open:
                            deadline = parse_dt(notice.get("submittingOffersDate"))
                            if deadline is not None and deadline < now:
                                continue

                        # Lokalna weryfikacja CPV
                        if not matches_profile(notice, p.cpv_prefixes):
                            total_skipped_cpv += 1
                            continue

                        total_matched += 1
                        if not object_id:
                            continue

                        fp = fingerprint_notice(notice)
                        prev_fp = get_state_fingerprint(db_path, object_id)
                        now_iso = utc_now().isoformat()

                        print(
                            f"DEBUG tender_type={notice.get('tenderType')!r}  orderType={notice.get('orderType')!r}"
                        )

                        upsert_notice_and_state(
                            db_path,
                            p.name,
                            notice,
                            fp,
                            now_iso,
                        )

                        if prev_fp is None:
                            total_new += 1
                            ted_new += 1
                            print(
                                f"[NEW][TED] {object_id} | "
                                f"{(notice.get('orderObject') or '')[:80]} | "
                                f"CPV {(notice.get('cpvCode') or '')[:20]} | "
                                f"ORG {(notice.get('organizationName') or '')[:40]}"
                            )
                        elif prev_fp != fp:
                            total_changed += 1

                except Exception as e:
                    print(f"[TED ERROR] {e}")
                    if debug:
                        import traceback

                        traceback.print_exc()

                print(
                    f"  TED: {ted_count} ogłoszeń, "
                    f"{ted_new} nowych (po deduplikacji z Board/Search)"
                )

    print(
        f"\nDone. seen={total_seen}, matched={total_matched}, "
        f"new={total_new}, changed={total_changed}, "
        f"skipped_cpv={total_skipped_cpv}, "
        f"skipped_prov={total_skipped_prov}"
    )


if __name__ == "__main__":
    main()
