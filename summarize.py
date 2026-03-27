# summarize.py
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

import httpx

from ai_agent import (
    GEMINI_MODEL,
    LLM_BACKEND,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    detailed_summary_text,
    summarize_from_html,
)
from bzp_client import extract_bzp_text, fetch_notice_html
from ted_client import extract_text_from_ted_xml, fetch_ted_xml


def _get_ted_body(object_id: str, client: httpx.Client) -> str:
    """Selekcyjny parser XML — do streszczenia strukturalnego."""
    pub_number = object_id.removeprefix("ted-")
    if not pub_number:
        return ""
    print(f"    📥 Pobieram XML z TED: {pub_number}...")
    xml_text = fetch_ted_xml(pub_number, client=client)
    if not xml_text:
        print("    ⚠ Nie udało się pobrać XML")
        return ""
    body = extract_text_from_ted_xml(xml_text, lang="POL")
    if not body:
        body = extract_text_from_ted_xml(xml_text, lang="ENG")
    print(f"    📄 Wyciągnięto {len(body)} znaków z XML (selekcyjny)")
    return body


def _get_ted_body_full(object_id: str, client: httpx.Client) -> str:
    """Pełny tekst XML — do streszczenia szczegółowego."""
    import xml.etree.ElementTree as ET
    pub_number = object_id.removeprefix("ted-")
    if not pub_number:
        return ""
    xml_text = fetch_ted_xml(pub_number, client=client)
    if not xml_text:
        return ""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""
    parts, seen = [], set()
    for el in root.iter():
        if el.get("languageID") == "POL" and el.text and el.text.strip():
            t = el.text.strip()
            if t[:80] not in seen:
                seen.add(t[:80])
                parts.append(t)
    text = "\n\n".join(parts)
    print(f"    📄 Wyciągnięto {len(text)} znaków z XML (pełny)")
    return text


def _get_bzp_body(object_id: str, client: httpx.Client) -> str:
    print(f"    📥 Pobieram stronę BZP: {object_id[:20]}...")
    html = fetch_notice_html(object_id, client=client)
    if not html:
        print("    ⚠ Nie udało się pobrać strony BZP")
        return ""
    text = extract_bzp_text(html)
    print(f"    📄 Wyciągnięto {len(text)} znaków z BZP")
    return text


def _db_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_notices_needing_work(db_path: str, limit: int) -> list:
    """
    Zwraca ogłoszenia które potrzebują któregokolwiek ze streszczeń:
    - bez streszczenia strukturalnego (summary_json = '{}' lub brak)
    - bez streszczenia szczegółowego (detailed_text IS NULL lub '')
    Pomija odrzucone (user_status = 'dismissed').
    """
    conn = _db_conn(db_path)
    rows = conn.execute("""
        SELECT n.*,
               s.summary_json,
               s.detailed_text,
               s.updated_at as sum_updated_at
        FROM notices n
        LEFT JOIN summaries s ON s.object_id = n.object_id
        WHERE n.user_status != 'dismissed' OR n.user_status IS NULL
          AND (
              s.object_id IS NULL
              OR n.updated_at > s.updated_at
              OR s.summary_json = '{}'
              OR s.summary_json IS NULL
              OR s.detailed_text IS NULL
              OR s.detailed_text = ''
          )
        ORDER BY n.updated_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def upsert_structural(db_path: str, object_id: str, profile_name: str,
                      summary: dict, model_name: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _db_conn(db_path)
    conn.execute("""
        INSERT INTO summaries(object_id, profile_name, summary_json, model_name, created_at, updated_at)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(object_id) DO UPDATE SET
            profile_name=excluded.profile_name,
            summary_json=excluded.summary_json,
            model_name=excluded.model_name,
            updated_at=excluded.updated_at
    """, (object_id, profile_name,
          json.dumps(summary, ensure_ascii=False),
          model_name, now, now))
    conn.commit()
    conn.close()


def upsert_detailed(db_path: str, object_id: str, profile_name: str,
                    detailed_text: str, model_name: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _db_conn(db_path)
    # Sprawdź czy wiersz istnieje
    exists = conn.execute(
        "SELECT 1 FROM summaries WHERE object_id=?", (object_id,)
    ).fetchone()
    if exists:
        conn.execute("""
            UPDATE summaries SET detailed_text=?, updated_at=?
            WHERE object_id=?
        """, (detailed_text, now, object_id))
    else:
        conn.execute("""
            INSERT INTO summaries(object_id, profile_name, summary_json,
                                  model_name, created_at, updated_at, detailed_text)
            VALUES(?,?,?,?,?,?,?)
        """, (object_id, profile_name, '{}', model_name, now, now, detailed_text))
    conn.commit()
    conn.close()


def main():
    db_path = os.getenv("TENDERBOT_DB", "data/tenderbot.sqlite")
    limit = int(os.getenv("TENDERBOT_SUMMARY_BATCH", "10"))
    backend = os.getenv("TENDERBOT_LLM_BACKEND", LLM_BACKEND)

    if backend == "ollama":
        print(f"Backend: Ollama | host: {OLLAMA_HOST} | model: {OLLAMA_MODEL}")
    elif backend == "gemini":
        print(f"Backend: Gemini | model: {GEMINI_MODEL}")

    model_label = (
        f"ollama:{OLLAMA_MODEL}" if backend == "ollama"
        else f"gemini:{GEMINI_MODEL}"
    )

    rows = get_notices_needing_work(db_path, limit)
    if not rows:
        print("Brak ogłoszeń do streszczenia.")
        return

    print(f"Ogłoszeń do przetworzenia: {len(rows)}")

    ok_struct = ok_detail = fail_struct = fail_detail = 0

    with httpx.Client(timeout=30.0) as http_client:
        for i, r in enumerate(rows):
            object_id = r["object_id"]
            title = (r["order_object"] or "")[:80]
            has_struct = r["summary_json"] and r["summary_json"] != "{}"
            has_detail = bool(r["detailed_text"])

            print(f"\n  [{i+1}/{len(rows)}] {object_id} | {title}")
            print(f"    struct={'✓' if has_struct else '✗'}  detail={'✓' if has_detail else '✗'}")

            # Pobierz treść — osobno dla strukturalnego i szczegółowego
            body = ""       # selekcyjny — do strukturalnego
            body_full = ""  # pełny XML/HTML — do szczegółowego

            if not has_struct or not has_detail:
                if object_id.startswith("ted-"):
                    if not has_struct:
                        body = _get_ted_body(object_id, http_client)
                    if not has_detail:
                        body_full = _get_ted_body_full(object_id, http_client)
                else:
                    # BZP — ta sama treść HTML dla obu
                    body = _get_bzp_body(object_id, http_client)
                    body_full = body

            # ── Streszczenie strukturalne ──
            if not has_struct:
                try:
                    summary = summarize_from_html(
                        order_object=r["order_object"],
                        organization_name=r["organization_name"],
                        cpv_code=r["cpv_code"],
                        submitting_offers_date=r["submitting_offers_date"],
                        html_body=body,
                        backend=backend,
                    )
                    upsert_structural(db_path, object_id, r["profile_name"],
                                      summary.model_dump(), model_label)
                    ok_struct += 1
                    print(f"    ✓ struct: {summary.title[:55]}")
                except Exception as e:
                    fail_struct += 1
                    print(f"    ✗ struct: {type(e).__name__}: {e}")
            else:
                print(f"    — struct: już istnieje")

            # ── Streszczenie szczegółowe ──
            if not has_detail:
                try:
                    if not body_full:
                        # Mogło nie być pobrane (struct już istniała)
                        if object_id.startswith("ted-"):
                            body_full = _get_ted_body_full(object_id, http_client)
                        else:
                            body_full = _get_bzp_body(object_id, http_client)

                    if body_full.strip():
                        detail = detailed_summary_text(body_full, backend=backend)
                        upsert_detailed(db_path, object_id, r["profile_name"],
                                        detail, model_label)
                        ok_detail += 1
                        print(f"    ✓ detail: {len(detail)} znaków")
                    else:
                        print(f"    ⚠ detail: brak treści do streszczenia")
                except Exception as e:
                    fail_detail += 1
                    print(f"    ✗ detail: {type(e).__name__}: {e}")
            else:
                print(f"    — detail: już istnieje")

    print(f"\nDone.")
    print(f"  Strukturalne: ok={ok_struct}, fail={fail_struct}")
    print(f"  Szczegółowe:  ok={ok_detail}, fail={fail_detail}")


if __name__ == "__main__":
    main()
