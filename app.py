# app_streamlit.py
"""
TenderBot — panel Streamlit.

Layout:
  Sidebar:  profile CRUD, sterowanie jobami
  Main:     lista ogłoszeń + streszczenia AI
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from rag import ask, build_fts_index

# =========================
# Paths / DB
# =========================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB = str(DATA_DIR / "tenderbot.sqlite")

CPV_CSV = str(BASE_DIR / "cpv_2008_ver_2013.csv")

EZ_NOTICE_URL = (
    "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{object_id}"
)
TED_NOTICE_URL = "https://ted.europa.eu/pl/notice/-/detail/{pub_number}"

st.set_page_config(
    page_title="TenderBot",
    page_icon="📋",
    layout="wide",
)


# =========================
# CPV helpers + loader
# =========================


def cpv_digits(code: str) -> str:
    return re.sub(r"\D", "", code or "")


def cpv8(code: str) -> str:
    d = cpv_digits(code)
    return d[:8] if len(d) >= 8 else d


@st.cache_data(show_spinner=False)
def load_cpv_map(csv_path: str) -> dict[str, str]:
    if not Path(csv_path).exists():
        return {}
    df = pd.read_csv(csv_path, sep=";", dtype=str, engine="python")
    df = df.dropna(subset=["CODE", "PL"])
    out: dict[str, str] = {}
    for code, pl in zip(df["CODE"], df["PL"]):
        key = cpv8(str(code))
        out[key] = str(pl).strip()
    return out


CPV_MAP = load_cpv_map(CPV_CSV)


# =========================
# Other helpers
# =========================


def run_script(script_name: str, extra_env: dict | None = None) -> tuple[int, str]:
    """Uruchamia skrypt i streamuje output linia po linii do st.status."""
    env = os.environ.copy()
    env["TENDERBOT_DB"] = DB
    env["PYTHONUNBUFFERED"] = "1"  # natychmiastowy flush stdout
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    cmd = [sys.executable, str(BASE_DIR / script_name)]

    lines: list[str] = []
    with st.status(f"🔄 {script_name}...", expanded=True) as status:
        log_area = st.empty()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            # Pokaż ostatnie 60 linii (żeby nie zamulać)
            visible = "\n".join(lines[-60:])
            log_area.code(visible, language="text")
        proc.wait()

        rc = proc.returncode
        if rc == 0:
            status.update(label=f"✅ {script_name} — OK", state="complete")
        else:
            status.update(
                label=f"❌ {script_name} — błąd (rc={rc})",
                state="error",
            )

    return rc, "\n".join(lines)


# =========================
# Dictionaries / defaults
# =========================

PROVINCES = {
    "PL02": "dolnośląskie",
    "PL04": "kujawsko-pomorskie",
    "PL06": "lubelskie",
    "PL08": "lubuskie",
    "PL10": "łódzkie",
    "PL12": "małopolskie",
    "PL14": "mazowieckie",
    "PL16": "opolskie",
    "PL18": "podkarpackie",
    "PL20": "podlaskie",
    "PL22": "pomorskie",
    "PL24": "śląskie",
    "PL26": "świętokrzyskie",
    "PL28": "warmińsko-mazurskie",
    "PL30": "wielkopolskie",
    "PL32": "zachodniopomorskie",
}

# Kody ISO3 krajów UE/EOG dla TED API (buyer-country)
EU_COUNTRIES = {
    "POL": "🇵🇱 Polska",
    "DEU": "🇩🇪 Niemcy",
    "FRA": "🇫🇷 Francja",
    "ITA": "🇮🇹 Włochy",
    "ESP": "🇪🇸 Hiszpania",
    "NLD": "🇳🇱 Holandia",
    "BEL": "🇧🇪 Belgia",
    "AUT": "🇦🇹 Austria",
    "CZE": "🇨🇿 Czechy",
    "SVK": "🇸🇰 Słowacja",
    "HUN": "🇭🇺 Węgry",
    "ROU": "🇷🇴 Rumunia",
    "BGR": "🇧🇬 Bułgaria",
    "HRV": "🇭🇷 Chorwacja",
    "SVN": "🇸🇮 Słowenia",
    "LTU": "🇱🇹 Litwa",
    "LVA": "🇱🇻 Łotwa",
    "EST": "🇪🇪 Estonia",
    "FIN": "🇫🇮 Finlandia",
    "SWE": "🇸🇪 Szwecja",
    "DNK": "🇩🇰 Dania",
    "IRL": "🇮🇪 Irlandia",
    "PRT": "🇵🇹 Portugalia",
    "GRC": "🇬🇷 Grecja",
    "CYP": "🇨🇾 Cypr",
    "MLT": "🇲🇹 Malta",
    "LUX": "🇱🇺 Luksemburg",
    "NOR": "🇳🇴 Norwegia",
    "ISL": "🇮🇸 Islandia",
    "LIE": "🇱🇮 Liechtenstein",
    "CHE": "🇨🇭 Szwajcaria",
}

DEFAULT_CPV_PRESETS = [
    # IT core
    "72000000",  # usługi informatyczne (cała grupa 72*)
    "48000000",  # pakiety oprogramowania (cała grupa 48*)
    # ITS / NeuroCar
    "34970000",  # urządzenia monitorowania ruchu
    "34923000",  # kontrola ruchu drogowego
    "34996000",  # urządzenia kontrolne dróg
    "35125300",  # kamery bezpieczeństwa (ANPR)
    "32323500",  # systemy nadzoru wideo
    # Rozszerzony
    "38750000",  # ważenie pojazdów (WIM)
    "34711200",  # drony / UAV
]


# =========================
# DB init + profile CRUD
# =========================


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS filter_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        enabled INTEGER NOT NULL,
        order_type TEXT NOT NULL,
        cpv_prefixes TEXT NOT NULL,
        provinces TEXT NOT NULL,
        countries TEXT NOT NULL DEFAULT '["POL"]',
        updated_at TEXT NOT NULL
    )""")
    conn.execute("""
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
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS summaries (
        object_id TEXT PRIMARY KEY,
        profile_name TEXT NOT NULL,
        summary_json TEXT NOT NULL,
        model_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ignored_cpv (
        cpv_code TEXT PRIMARY KEY,
        description TEXT,
        ignored_at TEXT NOT NULL
    )""")

    # Migracje
    cur = conn.cursor()
    cols_p = {r[1] for r in cur.execute("PRAGMA table_info(filter_profiles)")}
    if "countries" not in cols_p:
        cur.execute(
            "ALTER TABLE filter_profiles ADD COLUMN countries TEXT"
            " NOT NULL DEFAULT '[\"POL\"]'"
        )
    cols_n = {r[1] for r in cur.execute("PRAGMA table_info(notices)")}
    if "user_status" not in cols_n:
        cur.execute("ALTER TABLE notices ADD COLUMN user_status TEXT")
    if "is_below_eu" not in cols_n:
        cur.execute("ALTER TABLE notices ADD COLUMN is_below_eu INTEGER")
    if "tender_id" not in cols_n:
        cur.execute("ALTER TABLE notices ADD COLUMN tender_id TEXT")
    # Fix: TED notices zawsze EU, BZP bez flagi → krajowe
    cur.execute("""
        UPDATE notices SET is_below_eu = 0
        WHERE object_id LIKE 'ted-%' AND is_below_eu IS NULL
    """)
    cur.execute("""
        UPDATE notices SET is_below_eu = 1
        WHERE object_id NOT LIKE 'ted-%' AND is_below_eu IS NULL
    """)
    # Migracja: detailed_text w summaries
    cols_s = {r[1] for r in cur.execute("PRAGMA table_info(summaries)")}
    if "detailed_text" not in cols_s:
        cur.execute("ALTER TABLE summaries ADD COLUMN detailed_text TEXT")
    conn.commit()

    return conn


def upsert_profile(name, enabled, order_types, cpv_prefixes, provinces, countries):
    conn = db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO filter_profiles(name, enabled, order_type,
                                    cpv_prefixes, provinces,
                                    countries, updated_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
          enabled=excluded.enabled,
          order_type=excluded.order_type,
          cpv_prefixes=excluded.cpv_prefixes,
          provinces=excluded.provinces,
          countries=excluded.countries,
          updated_at=excluded.updated_at
        """,
        (
            name,
            1 if enabled else 0,
            json.dumps(order_types, ensure_ascii=False),
            json.dumps(cpv_prefixes, ensure_ascii=False),
            json.dumps(provinces, ensure_ascii=False),
            json.dumps(countries, ensure_ascii=False),
            now,
        ),
    )
    conn.commit()
    conn.close()


def delete_profile(name: str):
    conn = db()
    conn.execute("DELETE FROM filter_profiles WHERE name = ?", (name,))
    conn.commit()
    conn.close()


def load_profiles():
    conn = db()
    rows = conn.execute(
        """
        SELECT name, enabled, order_type, cpv_prefixes, provinces,
               countries, updated_at
        FROM filter_profiles
        ORDER BY updated_at DESC
        """
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        raw_countries = r[5]
        try:
            countries = json.loads(raw_countries) if raw_countries else ["POL"]
        except (json.JSONDecodeError, TypeError):
            countries = ["POL"]

        # order_type: backward compat — stary string → lista
        raw_ot = r[2] or ""
        try:
            order_types = json.loads(raw_ot)
            if isinstance(order_types, str):
                # Stary format: "Services" → ["Services"]
                order_types = [order_types] if order_types else []
        except (json.JSONDecodeError, TypeError):
            # Stary format: "Services" / "" → lista
            order_types = [raw_ot] if raw_ot else []

        out.append(
            {
                "name": r[0],
                "enabled": bool(r[1]),
                "order_types": order_types,
                "cpv_prefixes": json.loads(r[3]),
                "provinces": json.loads(r[4]),
                "countries": countries,
                "updated_at": r[6],
            }
        )
    return out


# =========================
# Ignored CPV CRUD
# =========================


def load_ignored_cpv() -> dict[str, str]:
    """Zwraca dict {cpv_code: description} ignorowanych kodów."""
    conn = db()
    rows = conn.execute(
        "SELECT cpv_code, description FROM ignored_cpv ORDER BY cpv_code"
    ).fetchall()
    conn.close()
    return {r[0]: r[1] or "" for r in rows}


def ignore_cpv(cpv_code: str, description: str = "") -> None:
    conn = db()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO ignored_cpv(cpv_code, description, ignored_at)
           VALUES(?,?,?)
           ON CONFLICT(cpv_code) DO UPDATE SET
             description=excluded.description,
             ignored_at=excluded.ignored_at""",
        (cpv_code, description, now),
    )
    conn.commit()
    conn.close()


def restore_cpv(cpv_code: str) -> None:
    conn = db()
    conn.execute("DELETE FROM ignored_cpv WHERE cpv_code = ?", (cpv_code,))
    conn.commit()
    conn.close()


def fmt_cpv(code8: str) -> str:
    return f"{code8} — {CPV_MAP.get(code8, '')}"



def render_notice(r, conn, ignored_cpv_set, key_prefix="", flat=False):
    """Renderuje pojedyncze ogłoszenie jako expander z pełną treścią."""
    object_id = r["object_id"]
    is_eu = (r["is_below_eu"] == 0) or object_id.startswith("ted-")
    tag = "🇪🇺" if is_eu else "🇵🇱"
    has_sum = "🧠" if r["has_summary"] else ""
    user_status = r["user_status"]  # None / 'starred' / 'dismissed'
    star_tag = "⭐" if user_status == "starred" else ""

    title = r["order_object"] or "(brak tytułu)"
    org = r["organization_name"] or ""
    deadline = r["submitting_offers_date"] or ""
    notice_num = r["notice_number"] or ""

    # Deadline — kolorowanie
    deadline_txt = ""
    if deadline:
        try:
            dl = deadline.replace("Z", "+00:00")
            # TED format: "2026-02-26+01:00" (date+tz, no time)
            # fromisoformat parses this as naive 2026-02-26 01:00
            # Fix: insert T00:00:00 before timezone
            if re.match(r"^\d{4}-\d{2}-\d{2}[+-]\d{2}:\d{2}$", dl):
                dl = dl[:10] + "T00:00:00" + dl[10:]
            dt_deadline = datetime.fromisoformat(dl)
            if dt_deadline.tzinfo is None:
                dt_deadline = dt_deadline.replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            if dt_deadline > now_dt:
                days_left = (dt_deadline - now_dt).days
                deadline_txt = f"⏰ {deadline[:10]} ({days_left}d)"
            else:
                deadline_txt = f"❌ {deadline[:10]}"
        except Exception:
            deadline_txt = deadline[:10]

    header = f"{tag} {star_tag} {has_sum} **{title}**"
    subheader = f"{notice_num} · {org} · {deadline_txt}"

    _ctx = st.container(border=True) if flat else st.expander(header, expanded=False)
    with _ctx:
        if flat:
            st.markdown(header)
        st.caption(subheader)

        # Linki
        is_ted = object_id.startswith("ted-")
        if is_ted:
            pub_number = object_id.removeprefix("ted-")
            notice_url = TED_NOTICE_URL.format(pub_number=pub_number)
        else:
            notice_url = EZ_NOTICE_URL.format(object_id=object_id)

        mp_url = None
        pdf_url = None
        if is_ted:
            pub_number = object_id.removeprefix("ted-")
            pdf_url = f"https://ted.europa.eu/pl/notice/{pub_number}/pdfs"
        elif is_eu:
            try:
                payload = conn.execute(
                    "SELECT payload_json FROM notices WHERE object_id = ?",
                    (object_id,),
                ).fetchone()
                if payload:
                    pj = json.loads(payload["payload_json"])
                    pdf_url = pj.get("pdfUrl")
            except Exception:
                pass

        link_cols = st.columns(4)
        with link_cols[0]:
            try:
                st.link_button("🔗 Ogłoszenie", notice_url)
            except Exception:
                st.markdown(f"[🔗 Ogłoszenie]({notice_url})")
        with link_cols[1]:
            if mp_url:
                try:
                    st.link_button("📂 Postępowanie", mp_url)
                except Exception:
                    st.markdown(f"[📂 Postępowanie]({mp_url})")
        with link_cols[2]:
            if pdf_url:
                try:
                    st.link_button("📄 PDF (TED)", pdf_url)
                except Exception:
                    st.markdown(f"[📄 PDF (TED)]({pdf_url})")

        # Przycisk streszczenia szczegółowego (TED + BZP)
        detail_key = f"detail_{object_id}"
        with link_cols[3]:
            if st.button(
                "✍️ Popraw streszczenie",
                key=f"{key_prefix}btn_detail_{object_id}",
                use_container_width=True,
                help="Generuje nowe streszczenie szczegółowe (nadpisuje istniejące)",
            ):
                with st.spinner("Streszczam..."):
                    try:
                        from ai_agent import detailed_summary_text

                        # Pobierz treść
                        if is_ted:
                            import xml.etree.ElementTree as _ET

                            from ted_client import fetch_ted_xml

                            pub_num = object_id.removeprefix("ted-")
                            xml_text = fetch_ted_xml(pub_num)
                            if not xml_text:
                                st.error("Nie udało się pobrać XML z TED.")
                                raise RuntimeError("XML fetch failed")
                            _root = _ET.fromstring(xml_text)
                            _parts, _seen = [], set()
                            for _el in _root.iter():
                                if (
                                    _el.get("languageID") == "POL"
                                    and _el.text
                                    and _el.text.strip()
                                ):
                                    _t = _el.text.strip()
                                    if _t[:80] not in _seen:
                                        _seen.add(_t[:80])
                                        _parts.append(_t)
                            full_text = "\n\n".join(_parts)
                        else:
                            from bzp_client import (
                                extract_bzp_text,
                                fetch_notice_html,
                            )

                            raw_html = fetch_notice_html(object_id)
                            full_text = (
                                extract_bzp_text(raw_html) if raw_html else ""
                            )

                        if not full_text.strip():
                            st.warning("Brak treści do streszczenia.")
                            raise RuntimeError("Empty text")

                        backend = st.session_state.get("llm_backend", "ollama")
                        if backend == "ollama":
                            os.environ["OLLAMA_MODEL"] = st.session_state.get(
                                "ollama_model", ""
                            ) or os.environ.get("OLLAMA_MODEL", "")
                            os.environ["OLLAMA_HOST"] = st.session_state.get(
                                "ollama_host", ""
                            ) or os.environ.get("OLLAMA_HOST", "")
                            key = st.session_state.get("ollama_api_key", "")
                            if key:
                                os.environ["OLLAMA_API_KEY"] = key
                        else:
                            os.environ["GEMINI_MODEL"] = st.session_state.get(
                                "gemini_model", ""
                            ) or os.environ.get("GEMINI_MODEL", "")
                            key = st.session_state.get("google_api_key", "")
                            if key:
                                os.environ["GOOGLE_API_KEY"] = key

                        result = detailed_summary_text(full_text, backend=backend)
                        st.session_state[detail_key] = result

                        now_iso = datetime.now(timezone.utc).isoformat()
                        existing = conn.execute(
                            "SELECT object_id FROM summaries WHERE object_id = ?",
                            (object_id,),
                        ).fetchone()
                        if existing:
                            conn.execute(
                                "UPDATE summaries SET detailed_text = ? WHERE object_id = ?",
                                (result, object_id),
                            )
                        else:
                            conn.execute(
                                """INSERT INTO summaries(
                                    object_id, profile_name, summary_json, model_name,
                                    created_at, updated_at, detailed_text
                                ) VALUES(?,?,'{}',?,?,'2000-01-01T00:00:00',?)""",
                                (
                                    object_id,
                                    r["profile_name"],
                                    backend,
                                    now_iso,
                                    result,
                                ),
                            )
                        conn.commit()
                        st.rerun()
                    except Exception as e:
                        if "failed" not in str(e) and "Empty" not in str(e):
                            st.error(f"Błąd: {e}")

        # ─── Oznaczanie ⭐ / ❌ ───
        act_cols = st.columns([1, 1, 1, 4])
        with act_cols[0]:
            if user_status != "starred":
                if st.button(
                    "⭐ Wybierz", key=f"{key_prefix}star_{object_id}", use_container_width=True
                ):
                    conn.execute(
                        "UPDATE notices SET user_status = 'starred'"
                        " WHERE object_id = ?",
                        (object_id,),
                    )
                    conn.commit()
                    st.rerun()
            else:
                if st.button(
                    "↩ Cofnij ⭐",
                    key=f"{key_prefix}unstar_{object_id}",
                    use_container_width=True,
                ):
                    conn.execute(
                        "UPDATE notices SET user_status = NULL WHERE object_id = ?",
                        (object_id,),
                    )
                    conn.commit()
                    st.rerun()
        with act_cols[1]:
            if user_status != "dismissed":
                if st.button(
                    "❌ Odrzuć",
                    key=f"{key_prefix}dismiss_{object_id}",
                    use_container_width=True,
                    type="secondary",
                ):
                    conn.execute(
                        "UPDATE notices SET user_status = 'dismissed'"
                        " WHERE object_id = ?",
                        (object_id,),
                    )
                    conn.commit()
                    st.rerun()
            else:
                if st.button(
                    "↩ Przywróć",
                    key=f"{key_prefix}undismiss_{object_id}",
                    use_container_width=True,
                ):
                    conn.execute(
                        "UPDATE notices SET user_status = NULL WHERE object_id = ?",
                        (object_id,),
                    )
                    conn.commit()
                    st.rerun()

        # Meta
        cpv_raw = r["cpv_code"] or ""
        prov = r["organization_province"] or ""
        ntype = r["notice_type"] or ""
        st.caption(f"Woj: {prov} · Typ: {ntype} · Profil: {r['profile_name']}")

        # CPV kody — wyświetlane osobno z opcją ignorowania
        if cpv_raw:
            cpv_codes = [
                c.strip()
                for c in re.split(r"[,;]\s*", cpv_raw)
                if c.strip() and re.match(r"^\d{5,8}", c.strip())
            ]
            if cpv_codes:
                cpv_label_parts = []
                for c in cpv_codes:
                    c8 = c[:8]
                    desc = CPV_MAP.get(c8, "")
                    is_ign = c8 in ignored_cpv_set
                    tag = "~~" if is_ign else ""
                    label = f"{tag}`{c8}`{tag}"
                    if desc:
                        label += f" {desc}"
                    if is_ign:
                        label += " *(ignorowany)*"
                    cpv_label_parts.append(label)
                st.caption("CPV: " + " · ".join(cpv_label_parts))

                # Przycisk ignorowania — po jednym per kod
                cpv_unique = list(dict.fromkeys(c.strip()[:8] for c in cpv_codes))
                if len(cpv_unique) <= 6:
                    cpv_btn_cols = st.columns(min(len(cpv_unique), 4))
                    for idx, c8 in enumerate(cpv_unique):
                        col = cpv_btn_cols[idx % len(cpv_btn_cols)]
                        with col:
                            if c8 not in ignored_cpv_set:
                                desc = CPV_MAP.get(c8, c8)
                                if st.button(
                                    f"🚫 {c8}",
                                    key=f"{key_prefix}ign_{object_id}_{c8}",
                                    help=f"Ignoruj: {desc}",
                                ):
                                    ignore_cpv(c8, desc)
                                    st.rerun()
            else:
                st.caption(f"CPV: {cpv_raw}")

        # Streszczenie AI
        # Załaduj detailed_text z bazy jeśli nie ma w session_state
        detail_key = f"detail_{object_id}"
        if detail_key not in st.session_state:
            dt_row = conn.execute(
                "SELECT detailed_text FROM summaries WHERE object_id = ?",
                (object_id,),
            ).fetchone()
            if dt_row and dt_row["detailed_text"]:
                st.session_state[detail_key] = dt_row["detailed_text"]

        has_detail = detail_key in st.session_state
        if r["has_summary"] or has_detail:
            sum_row = None
            summary = {}
            if r["has_summary"]:
                sum_row = conn.execute(
                    "SELECT summary_json, model_name FROM summaries WHERE object_id = ?",
                    (object_id,),
                ).fetchone()
                if sum_row:
                    summary = json.loads(sum_row["summary_json"])
            # Puste '{}' to nie jest prawdziwe streszczenie
            has_struct = bool(summary and summary.get("scope"))

            if has_struct or has_detail:
                tab_names = []
                if has_struct:
                    tab_names.extend(["🧠 Streszczenie", "📋 JSON"])
                if has_detail:
                    tab_names.append("📋 Szczegółowe")

                tabs = st.tabs(tab_names)
                tab_idx = 0

                if has_struct:
                    with tabs[tab_idx]:
                        eu = summary.get("eu_funding") or summary.get(
                            "eu_project_hint"
                        )
                        if eu and eu is not True:
                            st.success(f"🇪🇺 {eu}")
                        elif eu is True:
                            st.success("🇪🇺 Projekt unijny")

                        st.write("**Przedmiot:**", summary.get("scope") or "—")

                        lots = summary.get("lots") or []
                        if lots:
                            st.write("**Części zamówienia:**")
                            for item in lots:
                                st.caption(f"📦 {item}")

                        params = []
                        if summary.get("estimated_value"):
                            params.append(
                                f"💰 Wartość: {summary['estimated_value']}"
                            )
                        if summary.get("execution_period"):
                            params.append(
                                f"⏱ Realizacja: {summary['execution_period']}"
                            )
                        if summary.get("deposit_required"):
                            params.append(
                                f"🔒 Wadium: {summary['deposit_required']}"
                            )
                        if params:
                            st.caption(" · ".join(params))

                        conds = (
                            summary.get("participation_conditions")
                            or summary.get("key_requirements")
                            or []
                        )
                        st.write("**Warunki udziału:**")
                        if conds:
                            for item in conds:
                                st.caption(f"• {item}")
                        else:
                            st.caption("—")

                        evals = summary.get("evaluation_criteria") or []
                        st.write("**Kryteria oceny:**")
                        if evals:
                            for item in evals:
                                st.caption(f"• {item}")
                        else:
                            st.caption("—")

                        risks = summary.get("risks_and_flags") or []
                        st.write("**Ryzyka / flagi:**")
                        if risks:
                            for item in risks:
                                st.caption(f"⚠️ {item}")
                        else:
                            st.caption("—")

                    tab_idx += 1
                    with tabs[tab_idx]:
                        st.json(summary)
                    tab_idx += 1

                if has_detail:
                    with tabs[tab_idx]:
                        st.markdown(st.session_state[f"detail_{object_id}"])


# ╔══════════════════════════════════════════════════════════╗
# ║                      SIDEBAR                             ║
# ╚══════════════════════════════════════════════════════════╝

with st.sidebar:
    st.title("📋 TenderBot")

    if not CPV_MAP:
        st.warning(
            "Nie wczytano słownika CPV. Upewnij się, że plik "
            "'cpv_2008_ver_2013.csv' jest obok app_streamlit.py."
        )

    # ─── Sterowanie jobami ───
    st.header("⚙️ Sterowanie")

    days_back = st.number_input(
        "Dni wstecz",
        min_value=1,
        max_value=365,
        value=7,
        step=1,
        help="Ile godzin wstecz szukać ogłoszeń (168 = 7 dni)",
    )

    # ─── LLM backend ───
    with st.expander("🤖 Model AI (streszczenia)"):
        llm_backend = st.selectbox(
            "Backend",
            ["ollama", "gemini"],
            index=0,
            key="llm_backend",
        )
        if llm_backend == "ollama":
            llm_host = st.text_input(
                "Host Ollama",
                value=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
                key="ollama_host",
            )
            llm_api_key = st.text_input(
                "API Key Ollama",
                value=os.environ.get("OLLAMA_API_KEY", ""),
                key="ollama_api_key",
                type="password",
                help="Wymagany dla cloud modeli",
            )
            # Pobierz listę modeli z Ollama
            _ollama_models = []
            try:
                from ollama import Client as _OllamaClient

                _headers = (
                    {"Authorization": f"Bearer {llm_api_key}"} if llm_api_key else {}
                )
                _oclient = _OllamaClient(
                    host=llm_host or "http://localhost:11434", headers=_headers
                )
                _ollama_models = [m["model"] for m in _oclient.list().get("models", [])]
            except Exception:
                pass

            _default_model = os.environ.get(
                "OLLAMA_MODEL", "mistral-large-3:675b-cloud"
            )
            if _ollama_models:
                _idx = (
                    _ollama_models.index(_default_model)
                    if _default_model in _ollama_models
                    else 0
                )
                llm_model = st.selectbox(
                    "Model Ollama",
                    options=_ollama_models,
                    index=_idx,
                    key="ollama_model",
                )
            else:
                llm_model = st.text_input(
                    "Model Ollama",
                    value=_default_model,
                    key="ollama_model",
                    help="Nie udało się pobrać listy modeli — wpisz ręcznie",
                )

    summary_batch = st.number_input(
        "Streszczenia na raz",
        min_value=1,
        max_value=500,
        value=10,
        step=5,
        help="Ile ogłoszeń streszczać w jednym uruchomieniu",
    )

    if st.button("▶️ Monitor", use_container_width=True):
        rc, out = run_script(
            "monitor.py",
            extra_env={
                "TENDERBOT_HOURS_BACK": int(days_back) * 24,
                "TENDERBOT_PAGE_SIZE": 100,
            },
        )
        st.session_state["last_job_output"] = out
        st.session_state["last_job_rc"] = rc
        st.rerun()

    if st.button("🧠 Summarize", use_container_width=True):
        summary_env = {
            "TENDERBOT_SUMMARY_BATCH": int(summary_batch),
            "TENDERBOT_LLM_BACKEND": llm_backend,
        }
        if llm_backend == "ollama":
            summary_env["OLLAMA_MODEL"] = llm_model
            summary_env["OLLAMA_HOST"] = llm_host
            if llm_api_key:
                summary_env["OLLAMA_API_KEY"] = llm_api_key
        else:
            summary_env["GEMINI_MODEL"] = llm_model
            if llm_api_key:
                summary_env["GOOGLE_API_KEY"] = llm_api_key

        rc, out = run_script("summarize.py", extra_env=summary_env)
        st.session_state["last_job_output"] = out
        st.session_state["last_job_rc"] = rc
        st.rerun()
        # Przebuduj indeks FTS po streszczeniu
        try:
            from rag import build_fts_index

            n = build_fts_index(DB)
            st.session_state["last_job_output"] += (
                f"\n\n🔍 Indeks FTS przebudowany ({n} streszczeń)."
            )
        except Exception as _e:
            st.session_state["last_job_output"] += f"\n\n⚠ Indeks FTS: {_e}"
        st.rerun()

    if "last_job_output" in st.session_state:
        with st.expander("📜 Ostatni log", expanded=False):
            st.code(st.session_state["last_job_output"], language="text")
            if st.session_state.get("last_job_rc", 0) != 0:
                st.error(f"Return code: {st.session_state['last_job_rc']}")

    st.divider()

    # ─── Profil ───
    st.header("📝 Profil filtrów")

    profiles = load_profiles()
    names = [p["name"] for p in profiles]

    selected = st.selectbox("Profil", ["➕ Nowy profil"] + names)

    # Resetuj widgety gdy zmienił się profil
    if st.session_state.get("_prev_profile") != selected:
        st.session_state["_prev_profile"] = selected
        for k in [
            "prof_countries",
            "prof_all_prov",
            "prof_provinces",
        ]:
            st.session_state.pop(k, None)

    if selected != "➕ Nowy profil":
        p = next(x for x in profiles if x["name"] == selected)
        default_name = p["name"]
        default_enabled = p["enabled"]
        default_order_types = p.get("order_types", ["Services"])
        default_cpv = p["cpv_prefixes"]
        default_prov = p["provinces"]
        default_countries = p.get("countries", ["POL"])
    else:
        default_name = ""
        default_enabled = True
        default_order_types = ["Services"]
        default_cpv = DEFAULT_CPV_PRESETS
        default_prov = []
        default_countries = ["POL"]

    name = st.text_input("Nazwa profilu", value=default_name)
    enabled = st.checkbox("Aktywny", value=default_enabled)

    # ─── Typ zamówienia ───
    ALL_ORDER_TYPES = {
        "Services": "🔧 Usługi",
        "Supplies": "📦 Dostawy",
        "Works": "🏗️ Roboty budowlane",
    }
    order_types = st.multiselect(
        "Typ zamówienia (puste = wszystkie)",
        options=list(ALL_ORDER_TYPES.keys()),
        default=[t for t in default_order_types if t in ALL_ORDER_TYPES],
        format_func=lambda k: ALL_ORDER_TYPES.get(k, k),
    )

    # ─── CPV picker ───
    st.subheader("CPV")

    IT_PREFIXES = ("72", "48")
    cpv_it = (
        sorted([k for k in CPV_MAP.keys() if k.startswith(IT_PREFIXES)])
        if CPV_MAP
        else []
    )
    cpv_other = (
        sorted([k for k in CPV_MAP.keys() if not k.startswith(IT_PREFIXES)])
        if CPV_MAP
        else []
    )

    st.caption("🧩 IT (72* i 48*)")
    it_default = [cpv8(x) for x in default_cpv if cpv8(x) in set(cpv_it)]
    cpv_it_selected = st.multiselect(
        "Kody IT",
        options=cpv_it,
        default=it_default,
        format_func=fmt_cpv,
        disabled=not bool(CPV_MAP),
        label_visibility="collapsed",
    )

    COMMON_IT = [
        "72000000",
        "72110000",
        "72200000",
        "72300000",
        "72400000",
        "72500000",
        "72600000",
        "72700000",
        "72800000",
        "72900000",
        "48000000",
    ]
    if st.checkbox("✅ Preset IT", value=False, disabled=not bool(CPV_MAP)):
        for c in COMMON_IT:
            if c in cpv_it and c not in cpv_it_selected:
                cpv_it_selected.append(c)

    with st.expander("📚 Inne kody CPV"):
        q = st.text_input("Szukaj (kod lub opis)", value="", disabled=not bool(CPV_MAP))
        other_options = cpv_other
        if CPV_MAP and q.strip():
            qq = q.strip().lower()
            other_options = [
                c
                for c in cpv_other
                if qq in c.lower() or qq in CPV_MAP.get(c, "").lower()
            ][:500]

        other_default = [cpv8(x) for x in default_cpv if cpv8(x) in set(cpv_other)]
        cpv_other_selected = st.multiselect(
            "Inne kody",
            options=other_options,
            default=other_default,
            format_func=fmt_cpv,
            disabled=not bool(CPV_MAP),
            label_visibility="collapsed",
        )

    st.caption("✍️ Ręczne prefixy (przecinkami)")
    manual_default = [x for x in default_cpv if cpv8(x) not in CPV_MAP]
    cpv_custom_raw = st.text_input(
        "Dopisz prefixy",
        value=",".join(manual_default),
        label_visibility="collapsed",
    )

    custom_prefixes: list[str] = []
    for part in cpv_custom_raw.split(","):
        pfx = cpv_digits(part.strip())
        if not pfx:
            continue
        custom_prefixes.append(pfx[:8] if len(pfx) >= 8 else pfx)

    cpv_all: list[str] = []
    for x in cpv_it_selected + cpv_other_selected + custom_prefixes:
        if x and x not in cpv_all:
            cpv_all.append(x)

    with st.expander(f"👁️ Wybrane CPV ({len(cpv_all)})"):
        for c in cpv_all:
            desc = CPV_MAP.get(c, "(prefix)")
            st.caption(f"• {c} — {desc}")

    # ─── Kraje (TED) ───
    st.subheader("🌍 Kraje")
    st.caption("Polska (POL) = Board/Search + TED. Pozostałe = tylko TED.")
    countries = st.multiselect(
        "Kraje",
        options=list(EU_COUNTRIES.keys()),
        default=[c for c in default_countries if c in EU_COUNTRIES],
        format_func=lambda k: EU_COUNTRIES.get(k, k),
        label_visibility="collapsed",
        key="prof_countries",
    )
    if not countries:
        countries = ["POL"]

    # ─── Województwa (tylko gdy POL) ───
    if "POL" in countries:
        st.subheader("Województwa")
        st.caption("Dotyczy tylko polskich ogłoszeń (Board/Search + TED PL).")
        all_prov = st.checkbox(
            "Wszystkie",
            value=(len(default_prov) == 0),
            key="prof_all_prov",
        )
        if all_prov:
            provinces = []
        else:
            provinces = st.multiselect(
                "Wybierz",
                options=list(PROVINCES.keys()),
                format_func=lambda k: f"{PROVINCES[k]} ({k})",
                default=default_prov,
                label_visibility="collapsed",
                key="prof_provinces",
            )
    else:
        provinces = []

    # ─── Zapis / usuwanie ───
    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 Zapisz", use_container_width=True):
            if not name.strip():
                st.error("Podaj nazwę profilu.")
            else:
                upsert_profile(
                    name.strip(),
                    enabled,
                    order_types,
                    cpv_all,
                    provinces,
                    countries,
                )
                st.success("Zapisano.")
                st.rerun()

    with col_del:
        if selected != "➕ Nowy profil":
            if st.button("🗑️ Usuń", use_container_width=True, type="secondary"):
                delete_profile(selected)
                st.success(f"Usunięto: {selected}")
                st.rerun()

    # ─── Lista profili ───
    st.divider()
    st.subheader("Zapisane profile")
    for p in load_profiles():
        status = "🟢" if p["enabled"] else "🔴"
        prov_txt = ", ".join(p["provinces"]) if p["provinces"] else "wszystkie"
        countries_txt = ", ".join(p.get("countries", ["POL"]))
        ot_map = {"Services": "usługi", "Supplies": "dostawy", "Works": "roboty"}
        ots = p.get("order_types", [])
        ot_txt = ", ".join(ot_map.get(t, t) for t in ots) if ots else "wszystkie"
        st.caption(
            f"{status} **{p['name']}** — "
            f"Typ: {ot_txt} — "
            f"CPV: {len(p['cpv_prefixes'])} kodów — "
            f"Woj: {prov_txt} — "
            f"Kraje: {countries_txt}"
        )

    # ─── Ignorowane CPV ───
    st.divider()
    st.subheader("🚫 Ignorowane CPV")
    ignored = load_ignored_cpv()
    if ignored:
        st.caption(
            f"{len(ignored)} kodów ignorowanych — ogłoszenia z **tylko** "
            "ignorowanymi CPV są ukrywane."
        )
        for cpv_code, desc in ignored.items():
            icol1, icol2 = st.columns([4, 1])
            with icol1:
                label = CPV_MAP.get(cpv_code, desc or "")
                st.caption(f"`{cpv_code}` — {label}")
            with icol2:
                if st.button(
                    "↩", key=f"restore_cpv_{cpv_code}", help="Przywróć ten kod"
                ):
                    restore_cpv(cpv_code)
                    st.rerun()
    else:
        st.caption(
            "Brak ignorowanych kodów. Możesz ignorować kody "
            "klikając 🚫 przy kodzie CPV w ogłoszeniu."
        )


# ╔══════════════════════════════════════════════════════════╗
# ║                     MAIN PANEL                           ║
# ╚══════════════════════════════════════════════════════════╝

st.title("📋 Ogłoszenia")

conn = db()
conn.row_factory = sqlite3.Row

# ╔══════════════════════════════════════════════════════════╗
# ║     SEKCJA RAG — wklej zaraz po st.title("📋 Ogłoszenia")║
# ╚══════════════════════════════════════════════════════════╝


# ─── RAG ───
with st.expander("🔍 Zapytaj o ogłoszenia (RAG)", expanded=True):
    rag_col1, rag_col2 = st.columns([4, 1])
    with rag_col1:
        rag_question = st.text_input(
            "Pytanie",
            placeholder="np. Jakie ogłoszenia dotyczą rozpoznawania tablic rejestracyjnych?",
            label_visibility="collapsed",
            key="rag_question",
        )
    with rag_col2:
        rag_btn = st.button("🔍 Szukaj", use_container_width=True, key="rag_btn")

    rag_opts_col1, rag_opts_col2 = st.columns([2, 2])
    with rag_opts_col1:
        rag_include_expired = st.checkbox(
            "Uwzględnij zakończone", value=False, key="rag_include_expired"
        )
    with rag_opts_col2:
        if st.button("🔄 Przebuduj indeks FTS", use_container_width=True, key="rag_reindex"):
            with st.spinner("Indeksowanie..."):
                try:
                    n = build_fts_index(DB)
                    st.success(f"Zaindeksowano {n} streszczeń.")
                except Exception as e:
                    st.error(f"Błąd: {e}")

    if rag_btn and rag_question.strip():
        with st.spinner("Szukam i generuję odpowiedź..."):
            try:
                _rag_backend = st.session_state.get(
                    "llm_backend", os.getenv("TENDERBOT_LLM_BACKEND", "ollama")
                )
                rag_answer, rag_hits = ask(
                    db_path=DB,
                    question=rag_question.strip(),
                    top_n=999,
                    backend=_rag_backend,
                )
            except Exception as e:
                rag_answer = f"Błąd: {e}"
                rag_hits = []

        if not rag_include_expired:
            _now_iso = datetime.now(timezone.utc).isoformat()
            rag_hits = [
                h for h in rag_hits
                if not h.get("submitting_offers_date")
                or (h.get("submitting_offers_date") or "") >= _now_iso[:10]
            ]

        st.session_state["rag_answer"] = rag_answer
        st.session_state["rag_hits_ids"] = [h["object_id"] for h in rag_hits]

    if st.session_state.get("rag_answer"):
        st.markdown("**Odpowiedź:**")
        st.markdown(st.session_state["rag_answer"])
        _rag_ids = st.session_state.get("rag_hits_ids", [])
        if _rag_ids:
            _sort_col, _count_col = st.columns([2, 3])
            with _sort_col:
                _rag_sort = st.selectbox(
                    "Sortuj źródła",
                    [
                        "Trafność (domyślna)",
                        "⏰ Deadline (rosnąco)",
                        "⏰ Deadline (malejąco)",
                        "📅 Data publikacji (najnowsze)",
                        "⭐ Oznaczone najpierw",
                        "🇵🇱 Krajowe najpierw",
                        "🇪🇺 Unijne najpierw",
                        "📋 Typ zamówienia",
                    ],
                    key="rag_sort",
                    label_visibility="collapsed",
                )

            # Pobierz wszystkie wiersze
            _rag_ignored = load_ignored_cpv()
            _rag_rows = []
            for _oid in _rag_ids:
                _nr = conn.execute(
                    """SELECT n.*,
                       CASE WHEN s.object_id IS NOT NULL THEN 1 ELSE 0 END as has_summary
                       FROM notices n
                       LEFT JOIN summaries s ON s.object_id = n.object_id
                       WHERE n.object_id = ?""",
                    (_oid,),
                ).fetchone()
                if _nr:
                    _rag_rows.append(_nr)

            # Sortowanie
            _now_iso = datetime.now(timezone.utc).isoformat()
            def _deadline_key(r):
                d = r["submitting_offers_date"] or ""
                return d if d else "9999-99-99"

            if _rag_sort == "⏰ Deadline (rosnąco)":
                _rag_rows.sort(key=_deadline_key)
            elif _rag_sort == "⏰ Deadline (malejąco)":
                _rag_rows.sort(key=_deadline_key, reverse=True)
            elif _rag_sort == "📅 Data publikacji (najnowsze)":
                _rag_rows.sort(key=lambda r: r["publication_date"] or "", reverse=True)
            elif _rag_sort == "⭐ Oznaczone najpierw":
                _rag_rows.sort(key=lambda r: (0 if r["user_status"] == "starred" else 1))
            elif _rag_sort == "🇵🇱 Krajowe najpierw":
                _rag_rows.sort(key=lambda r: (0 if not r["object_id"].startswith("ted-") else 1))
            elif _rag_sort == "🇪🇺 Unijne najpierw":
                _rag_rows.sort(key=lambda r: (0 if r["object_id"].startswith("ted-") else 1))
            elif _rag_sort == "📋 Typ zamówienia":
                _rag_rows.sort(key=lambda r: r["tender_type"] or "")
            # "Trafność" — zachowaj oryginalną kolejność z FTS

            with _count_col:
                st.caption(f"**{len(_rag_rows)} ogłoszeń**")

            for _nr in _rag_rows:
                render_notice(_nr, conn, _rag_ignored, key_prefix="rag_", flat=True)


st.divider()


# ─── Filtry głównego panelu ───
fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns([1, 1, 1, 1, 1])

with fcol1:
    filter_eu = st.selectbox(
        "Procedura",
        ["Wszystkie", "Krajowe (BZP)", "Unijne (TED)"],
    )

with fcol2:
    _profile_options = ["Wszystkie"] + [p["name"] for p in profiles]
    _default_idx = 0
    if selected != "➕ Nowy profil" and selected in _profile_options:
        _default_idx = _profile_options.index(selected)
    filter_profile = st.selectbox(
        "Profil",
        _profile_options,
        index=_default_idx,
    )

with fcol3:
    filter_status = st.selectbox(
        "Status",
        ["Wszystkie", "Otwarte (deadline w przyszłości)", "Zakończone"],
        index=1,
    )

with fcol4:
    filter_mark = st.selectbox(
        "Oznaczenie",
        ["Aktywne", "⭐ Wybrane", "❌ Odrzucone", "Wszystkie"],
    )

with fcol5:
    filter_search = st.text_input("🔍 Szukaj w tytule/org", value="")

# Drugi rząd filtrów
fcol2_1, fcol2_2 = st.columns([1, 2])
with fcol2_1:
    FILTER_ORDER_TYPES = {
        "Wszystkie": None,
        "🔧 Usługi": "Services",
        "📦 Dostawy": "Supplies",
        "🏗️ Roboty budowlane": "Works",
    }
    filter_order_type = st.selectbox(
        "Typ zamówienia",
        options=list(FILTER_ORDER_TYPES.keys()),
    )
with fcol2_2:
    ignored_cpv_set = load_ignored_cpv()
    hide_ignored = st.checkbox(
        f"🚫 Ukryj ignorowane CPV ({len(ignored_cpv_set)})",
        value=True if ignored_cpv_set else False,
        disabled=not ignored_cpv_set,
    )

# Reset strony gdy zmienił się filtr
filter_key = (
    f"{filter_eu}|{filter_profile}|{filter_status}"
    f"|{filter_mark}|{filter_search}"
    f"|{filter_order_type}|{hide_ignored}"
)
if st.session_state.get("_filter_key") != filter_key:
    st.session_state["page"] = 0
    st.session_state["_filter_key"] = filter_key

# ─── Query builder ───
where_parts = []
params = []

# Oznaczenie (user_status)
if filter_mark == "Aktywne":
    where_parts.append("(n.user_status IS NULL OR n.user_status = 'starred')")
elif filter_mark == "⭐ Wybrane":
    where_parts.append("n.user_status = 'starred'")
elif filter_mark == "❌ Odrzucone":
    where_parts.append("n.user_status = 'dismissed'")

if filter_eu == "Krajowe (BZP)":
    where_parts.append(
        "(n.is_below_eu = 1 OR "
        "(n.is_below_eu IS NULL AND n.object_id NOT LIKE 'ted-%'))"
    )
elif filter_eu == "Unijne (TED)":
    where_parts.append("(n.is_below_eu = 0 OR n.object_id LIKE 'ted-%')")

if filter_profile != "Wszystkie":
    where_parts.append("n.profile_name = ?")
    params.append(filter_profile)

now_iso = datetime.now(timezone.utc).isoformat()
if filter_status == "Otwarte (deadline w przyszłości)":
    where_parts.append(
        "(n.submitting_offers_date IS NULL OR n.submitting_offers_date >= ?)"
    )
    params.append(now_iso)
elif filter_status == "Zakończone":
    where_parts.append(
        "(n.submitting_offers_date IS NOT NULL AND n.submitting_offers_date < ?)"
    )
    params.append(now_iso)

if filter_search.strip():
    where_parts.append("(n.order_object LIKE ? OR n.organization_name LIKE ?)")
    params.extend([f"%{filter_search.strip()}%"] * 2)

# Typ zamówienia (Services / Supplies / Works)
_filter_ot_val = FILTER_ORDER_TYPES.get(filter_order_type)
if _filter_ot_val:
    where_parts.append("n.tender_type = ?")
    params.append(_filter_ot_val)

# Ignorowane CPV — ukryj ogłoszenia zawierające ignorowany kod
if hide_ignored and ignored_cpv_set:
    where_parts.append(
        "NOT EXISTS ("
        "  SELECT 1 FROM ignored_cpv ic"
        "  WHERE n.cpv_code LIKE '%' || ic.cpv_code || '%'"
        ")"
    )

where_clause = " AND ".join(where_parts) if where_parts else "1=1"

# ─── Paginacja ───
PAGE_SIZE = 25
if "page" not in st.session_state:
    st.session_state["page"] = 0

# ─── Tabela ogłoszeń ───

try:
    total_row = conn.execute(
        f"""SELECT COUNT(*) as cnt FROM notices n
        LEFT JOIN summaries s ON s.object_id = n.object_id
        WHERE {where_clause}""",
        params,
    ).fetchone()
    total_count = total_row["cnt"]

    offset = st.session_state["page"] * PAGE_SIZE

    notices_rows = conn.execute(
        f"""
        SELECT
            n.object_id,
            n.notice_number,
            n.publication_date,
            n.order_object,
            n.organization_name,
            n.organization_city,
            n.organization_province,
            n.cpv_code,
            n.submitting_offers_date,
            n.notice_type,
            n.is_below_eu,
            n.profile_name,
            n.user_status,
            CASE WHEN s.object_id IS NOT NULL THEN 1 ELSE 0 END as has_summary
        FROM notices n
        LEFT JOIN summaries s ON s.object_id = n.object_id
        WHERE {where_clause}
        ORDER BY n.publication_date DESC
        LIMIT ? OFFSET ?
        """,
        params + [PAGE_SIZE, offset],
    ).fetchall()
except sqlite3.OperationalError as e:
    st.error(f"Błąd SQL: {e}")
    total_count = 0
    notices_rows = []

total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)

# ─── Statystyki ───
try:
    stats = conn.execute(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE
                WHEN n.is_below_eu = 1 THEN 1
                WHEN n.is_below_eu IS NULL AND n.object_id NOT LIKE 'ted-%' THEN 1
                ELSE 0 END) as pl_count,
            SUM(CASE
                WHEN n.is_below_eu = 0 THEN 1
                WHEN n.object_id LIKE 'ted-%' THEN 1
                ELSE 0 END) as eu_count,
            SUM(CASE WHEN s.object_id IS NOT NULL THEN 1 ELSE 0 END) as sum_count
        FROM notices n
        LEFT JOIN summaries s ON s.object_id = n.object_id
        WHERE {where_clause}
        """,
        params,
    ).fetchone()
    pl_count = stats["pl_count"] or 0
    eu_count = stats["eu_count"] or 0
    summary_count = stats["sum_count"] or 0
except sqlite3.OperationalError:
    pl_count = eu_count = summary_count = 0

# Star / dismissed counts (niezależne od filtru 'Oznaczenie')
starred_count = dismissed_count = 0
try:
    # where bez user_status
    no_mark_parts = [p for p in where_parts if "user_status" not in p]
    no_mark_where = " AND ".join(no_mark_parts) if no_mark_parts else "1=1"
    no_mark_params = [p for p in params]  # params nie zawierają user_status
    st_row = conn.execute(
        f"""SELECT
            SUM(CASE WHEN n.user_status = 'starred' THEN 1 ELSE 0 END) as starred,
            SUM(CASE WHEN n.user_status = 'dismissed' THEN 1 ELSE 0 END) as dismissed
        FROM notices n WHERE {no_mark_where}""",
        no_mark_params,
    ).fetchone()
    starred_count = st_row["starred"] or 0
    dismissed_count = st_row["dismissed"] or 0
except sqlite3.OperationalError:
    pass

mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)
mcol1.metric("Ogłoszenia", total_count)
mcol2.metric("🇵🇱 Krajowe", pl_count)
mcol3.metric("🇪🇺 Unijne", eu_count)
mcol4.metric("⭐ Wybrane", starred_count)
mcol5.metric("❌ Odrzucone", dismissed_count)
mcol6.metric("🧠 Streszczenia", summary_count)

st.divider()


if not notices_rows:
    st.info("Brak ogłoszeń w bazie. Kliknij ▶️ Monitor w panelu bocznym.")
else:
    for r in notices_rows:
        render_notice(r, conn, ignored_cpv_set)

    st.divider()
    pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
    with pcol1:
        if st.session_state["page"] > 0:
            if st.button("⬅️ Poprzednia", use_container_width=True):
                st.session_state["page"] -= 1
                st.rerun()
    with pcol2:
        current = st.session_state["page"] + 1
        st.caption(f"Strona {current} z {total_pages} ({total_count} ogłoszeń)")
    with pcol3:
        if st.session_state["page"] < total_pages - 1:
            if st.button("Następna ➡️", use_container_width=True):
                st.session_state["page"] += 1
                st.rerun()

conn.close()

