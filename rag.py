# rag.py
"""
RAG (Retrieval-Augmented Generation) dla TenderBot.

Źródło: streszczenia AI z tabeli summaries (summary_json + detailed_text)
Indeks:  SQLite FTS5 — bez zewnętrznych serwisów
Flow:    pytanie → FTS5 (top N streszczeń) → LLM → odpowiedź
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from typing import List, Optional


FTS_CREATE = """
CREATE VIRTUAL TABLE IF NOT EXISTS summaries_fts USING fts5(
    object_id,
    order_object,
    organization_name,
    title,
    scope,
    lots,
    participation_conditions,
    evaluation_criteria,
    risks_and_flags,
    estimated_value,
    execution_period,
    eu_funding,
    detailed_text,
    tokenize='unicode61'
);
"""


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def build_fts_index(db_path: str) -> int:
    """Buduje / przebudowuje indeks FTS5 ze streszczeń."""
    conn = _conn(db_path)
    conn.execute("DROP TABLE IF EXISTS summaries_fts")
    conn.execute(FTS_CREATE)

    rows = conn.execute("""
        SELECT
            s.object_id,
            n.order_object,
            n.organization_name,
            s.summary_json,
            s.detailed_text
        FROM summaries s
        LEFT JOIN notices n ON n.object_id = s.object_id
        WHERE s.summary_json IS NOT NULL AND s.summary_json != '{}'
    """).fetchall()

    count = 0
    for r in rows:
        try:
            sj = json.loads(r["summary_json"] or "{}")
        except Exception:
            sj = {}

        def _join(val) -> str:
            if isinstance(val, list):
                return " ".join(str(x) for x in val)
            return str(val) if val else ""

        conn.execute("""
            INSERT INTO summaries_fts(
                object_id, order_object, organization_name,
                title, scope, lots,
                participation_conditions, evaluation_criteria,
                risks_and_flags, estimated_value, execution_period,
                eu_funding, detailed_text
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["object_id"] or "",
            r["order_object"] or "",
            r["organization_name"] or "",
            sj.get("title") or "",
            sj.get("scope") or "",
            _join(sj.get("lots", [])),
            _join(sj.get("participation_conditions", [])),
            _join(sj.get("evaluation_criteria", [])),
            _join(sj.get("risks_and_flags", [])),
            sj.get("estimated_value") or "",
            sj.get("execution_period") or "",
            sj.get("eu_funding") or "",
            r["detailed_text"] or "",
        ))
        count += 1

    conn.commit()
    conn.close()
    return count


def _sanitize_query(query: str) -> str:
    q = re.sub(r'["\(\)\*\+\-\:\^]', ' ', query)
    q = re.sub(r'\s+', ' ', q).strip()
    return q or query


def search_fts(db_path: str, query: str, top_n: int = 6) -> List[dict]:
    """
    Przeszukuje FTS5. Przy braku wyników próbuje pojedyncze słowa,
    a następnie LIKE fallback na notices + summaries.
    """
    conn = _conn(db_path)

    has_fts = conn.execute("""
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='table' AND name='summaries_fts'
    """).fetchone()[0]

    if not has_fts:
        conn.close()
        return []

    safe_q = _sanitize_query(query)
    fts_rows = []

    # Próba 1: pełne zapytanie FTS
    try:
        fts_rows = conn.execute("""
            SELECT object_id, order_object, organization_name, rank
            FROM summaries_fts
            WHERE summaries_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (safe_q, top_n)).fetchall()
    except sqlite3.OperationalError:
        pass

    # Próba 2: pojedyncze słowa
    if not fts_rows:
        words = [w for w in safe_q.split() if len(w) >= 3]
        for word in words:
            try:
                fts_rows = conn.execute("""
                    SELECT object_id, order_object, organization_name, rank
                    FROM summaries_fts
                    WHERE summaries_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (word, top_n)).fetchall()
                if fts_rows:
                    break
            except sqlite3.OperationalError:
                continue

    # Próba 3: LIKE fallback na notices + summaries
    if not fts_rows:
        words = [w for w in safe_q.split() if len(w) >= 4]
        like_rows = []
        seen = set()
        for word in words[:3]:
            rows = conn.execute("""
                SELECT n.object_id, n.order_object, n.organization_name,
                       s.summary_json, s.detailed_text
                FROM notices n
                JOIN summaries s ON s.object_id = n.object_id
                WHERE n.order_object LIKE ? OR s.summary_json LIKE ?
                LIMIT ?
            """, (f"%{word}%", f"%{word}%", top_n)).fetchall()
            for r in rows:
                if r["object_id"] not in seen:
                    seen.add(r["object_id"])
                    like_rows.append(r)
            if len(like_rows) >= top_n:
                break

        results = []
        for r in like_rows[:top_n]:
            try:
                sj = json.loads(r["summary_json"] or "{}")
            except Exception:
                sj = {}
            results.append({
                "object_id": r["object_id"],
                "order_object": r["order_object"] or "",
                "organization_name": r["organization_name"] or "",
                "summary": sj,
                "detailed_text": r["detailed_text"] or "",
                "rank": 0,
            })
        conn.close()
        return results

    # Pobierz pełny summary_json dla wyników FTS
    results = []
    for r in fts_rows:
        oid = r["object_id"]
        srow = conn.execute(
            "SELECT summary_json, detailed_text FROM summaries WHERE object_id=?",
            (oid,)
        ).fetchone()
        try:
            sj = json.loads((srow["summary_json"] if srow else None) or "{}")
        except Exception:
            sj = {}
        results.append({
            "object_id": oid,
            "order_object": r["order_object"] or "",
            "organization_name": r["organization_name"] or "",
            "summary": sj,
            "detailed_text": (srow["detailed_text"] if srow else None) or "",
            "rank": r["rank"],
        })

    conn.close()
    return results


def _format_result(r: dict, idx: int) -> str:
    s = r["summary"]
    lines = [f"### Ogłoszenie {idx + 1}: {r['order_object'][:120]}"]
    lines.append(f"Zamawiający: {r['organization_name']}")
    if s.get("scope"):
        lines.append(f"Przedmiot: {s['scope']}")
    if s.get("lots"):
        lines.append(f"Części: {'; '.join(s['lots'][:3])}")
    if s.get("estimated_value"):
        lines.append(f"Wartość: {s['estimated_value']}")
    if s.get("execution_period"):
        lines.append(f"Czas realizacji: {s['execution_period']}")
    if s.get("participation_conditions"):
        lines.append(f"Warunki: {'; '.join(s['participation_conditions'][:3])}")
    if s.get("evaluation_criteria"):
        lines.append(f"Kryteria: {'; '.join(s['evaluation_criteria'][:3])}")
    if s.get("eu_funding"):
        lines.append(f"Finansowanie UE: {s['eu_funding']}")
    if s.get("risks_and_flags"):
        lines.append(f"Ryzyka: {'; '.join(s['risks_and_flags'][:2])}")
    if r["detailed_text"]:
        snippet = r["detailed_text"][:600].replace("\n", " ")
        lines.append(f"Szczegóły: {snippet}...")
    lines.append(f"ID: {r['object_id']}")
    return "\n".join(lines)


def build_context(results: List[dict]) -> str:
    if not results:
        return ""
    return "\n\n---\n\n".join(_format_result(r, i) for i, r in enumerate(results))


_RAG_SYSTEM = """Jesteś asystentem analizującym ogłoszenia przetargowe.
Na podstawie KONTEKSTU (fragmentów streszczeń ogłoszeń) odpowiedz na PYTANIE użytkownika.
- Odpowiadaj po polsku, zwięźle i konkretnie.
- Jeśli pytanie dotyczy konkretnych ogłoszeń, wymień je z nazwy/ID.
- Jeśli kontekst nie zawiera odpowiedzi, powiedz to wprost.
- Nie wymyślaj informacji spoza kontekstu.
"""


def ask(
    db_path: str,
    question: str,
    top_n: int = 6,
    backend: Optional[str] = None,
) -> tuple[str, List[dict]]:
    """Główna funkcja RAG. Zwraca (odpowiedź_llm, lista_wyników_fts)."""

    results = search_fts(db_path, question, top_n=top_n)
    if not results:
        return (
            "Nie znaleziono pasujących ogłoszeń. "
            "Spróbuj przeformułować pytanie lub kliknij 'Przebuduj indeks FTS'.",
            []
        )

    context = build_context(results)
    user_msg = f"PYTANIE: {question}\n\nKONTEKST:\n\n{context}"
    chosen = (backend or os.getenv("TENDERBOT_LLM_BACKEND", "ollama")).lower()

    if chosen == "ollama":
        try:
            from ollama import Client as OllamaClient
        except ImportError:
            return "Brak biblioteki ollama.", results

        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
        api_key = os.getenv("OLLAMA_API_KEY", "")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        client = OllamaClient(host=host, headers=headers)
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": _RAG_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            options={"temperature": 0.3},
        )
        answer = resp["message"]["content"]
        answer = re.sub(r"<think>[\s\S]*?</think>", "", answer).strip()
        answer = re.sub(r"<think>[\s\S]*", "", answer).strip()

    elif chosen == "gemini":
        try:
            from google import genai
        except ImportError:
            return "Brak biblioteki google-genai.", results

        api_key = os.getenv("GOOGLE_API_KEY", "")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents=_RAG_SYSTEM + "\n\n" + user_msg,
        )
        answer = getattr(resp, "text", None) or str(resp)
    else:
        return f"Nieznany backend: {chosen}", results

    return answer, results
