# ai_agent.py
"""
Moduł streszczania ogłoszeń przetargowych.

Obsługiwane backendy:
  - ollama  — tradycyjna biblioteka ollama (lokalne lub cloud modele
              pobrane przez `ollama pull`, np. `ollama pull kimi-k2.5:cloud`)
              Host konfigurowany przez OLLAMA_HOST (domyślnie http://localhost:11434)
  - gemini  — Google Gemini API (wymaga GOOGLE_API_KEY)

Wybór backendu: zmienna TENDERBOT_LLM_BACKEND = "ollama" | "gemini"
"""
from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

# ── Ollama (tradycyjna biblioteka) ──
try:
    from ollama import Client as OllamaClient
except ImportError:
    OllamaClient = None

# ── Gemini ──
try:
    from google import genai
except ImportError:
    genai = None

# ── Konfiguracja ──
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "kimi-k2.5:cloud")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Domyślny backend: ollama
LLM_BACKEND = os.getenv("TENDERBOT_LLM_BACKEND", "ollama")


# =========================
# Schemat wyniku
# =========================

class TenderSummary(BaseModel):
    # ── Identyfikacja ──
    title: str = Field(
        default="(brak tytułu)",
        description="Krótki tytuł zamówienia (1 linia)",
    )
    contracting_authority: Optional[str] = Field(
        None, description="Zamawiający"
    )
    cpv_main: Optional[str] = Field(
        None, description="Główny CPV (jeśli da się ustalić)"
    )
    submission_deadline: Optional[str] = Field(
        None, description="Termin składania ofert"
    )

    # ── Przedmiot ──
    scope: str = Field(
        default="",
        description="2-5 zdań o przedmiocie zamówienia (co kupujesz)",
    )
    lots: List[str] = Field(
        default_factory=list,
        description=(
            "Części zamówienia — krótki opis każdej części, np. "
            "'Część 1: Elektronika i multimedia (24 390 zł)'"
        ),
    )

    # ── Parametry ──
    estimated_value: Optional[str] = Field(
        None,
        description="Szacunkowa wartość zamówienia (łączna lub per lot)",
    )
    execution_period: Optional[str] = Field(
        None,
        description="Czas realizacji, np. '21 dni', '12 miesięcy'",
    )
    deposit_required: Optional[str] = Field(
        None,
        description=(
            "Wadium / zabezpieczenie — kwota lub 'nie wymagane'. "
            "Np. '5% ceny oferty', '10 000 zł'"
        ),
    )

    # ── Warunki udziału ──
    participation_conditions: List[str] = Field(
        default_factory=list,
        description=(
            "Warunki udziału w postępowaniu (co musisz mieć jako firma): "
            "zdolność finansowa, doświadczenie, uprawnienia, kadra. "
            "NIE wpisuj tu standardowych podstaw wykluczenia PZP."
        ),
    )

    # ── Kryteria oceny ──
    evaluation_criteria: List[str] = Field(
        default_factory=list,
        description=(
            "Kryteria oceny ofert z wagami, np. "
            "'Cena 60%', 'Gwarancja 40%'"
        ),
    )

    # ── Finansowanie UE ──
    eu_funding: Optional[str] = Field(
        None,
        description=(
            "Nazwa programu / funduszu UE jeśli zamówienie jest "
            "dofinansowane (np. 'FERC 2021-2027', 'KPO', "
            "'Fundusze Europejskie dla Wielkopolski'). "
            "Null jeśli brak wzmianek."
        ),
    )

    # ── Ryzyka ──
    risks_and_flags: List[str] = Field(
        default_factory=list,
        description=(
            "Realne ryzyka i flagi dla oferenta. "
            "NIE wpisuj standardowych artykułów PZP (108/109). "
            "Przykłady: krótki termin, nietypowe wymagania, "
            "odrzucenie oferty przy X, kary umowne."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_nulls(cls, values):
        """Zamienia None na domyślne wartości dla wymaganych pól."""
        if isinstance(values, dict):
            if values.get("title") is None:
                values["title"] = "(brak tytułu)"
            if values.get("scope") is None:
                values["scope"] = ""
            # Backward compat: stary schemat → nowy
            if "key_requirements" in values and "participation_conditions" not in values:
                values["participation_conditions"] = values.pop("key_requirements")
            if "eu_project_hint" in values and "eu_funding" not in values:
                hint = values.pop("eu_project_hint")
                if hint and not values.get("eu_funding"):
                    values["eu_funding"] = "(tak — brak szczegółów)"
        return values


# =========================
# Helpery
# =========================

def strip_html_to_text(html: str) -> str:
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_json(text: str) -> dict:
    text = (text or "").strip()

    # Strip thinking tags (kimi, deepseek, qwen3)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    # Unclosed <think> — strip from start
    text = re.sub(r"<think>[\s\S]*", "", text).strip()

    # 1. Czysty JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2. JSON w bloku markdown ```json ... ```
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.I)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # 3. Pierwszy obiekt JSON w tekście
    m = re.search(r"(\{[\s\S]*\})", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            # 4. Może JSON jest ucięty — spróbuj naprawić
            raw = m.group(1).strip()
            # Zamknij niezamknięte stringi i tablice
            suffixes = ['"}', '"]', '"]}', '"}]', '"}]}']
            for fix in suffixes:
                try:
                    return json.loads(raw + fix)
                except Exception:
                    pass

    # Pokaż fragment odpowiedzi w błędzie
    preview = text[:300] if len(text) > 300 else text
    raise ValueError(
        f"Nie udało się wyciągnąć JSON z odpowiedzi modelu.\n"
        f"Odpowiedź ({len(text)} zn.): {preview!r}"
    )


# =========================
# Prompt
# =========================

def build_prompt(
    order_object: str | None,
    organization_name: str | None,
    cpv_code: str | None,
    submitting_offers_date: str | None,
    html_body: str,
) -> tuple[str, str]:
    system = (
        "Zwróć WYŁĄCZNIE poprawny JSON. "
        "Bez markdown, bez wyjaśnień. /no_think"
    )

    text = strip_html_to_text(html_body or "")[:25000]

    content_section = f"TREŚĆ:\n{text}" if text.strip() else (
        "Brak treści. Wypełnij na podstawie META."
    )

    user = f"""Streszcz ogłoszenie zamówienia publicznego. Zwróć TYLKO JSON:
{{"title":"krótki tytuł","contracting_authority":"zamawiający|null","cpv_main":"kod|null","submission_deadline":"termin|null","scope":"2-3 zdania: co kupujesz","lots":["Część N: opis (kwota)"],"estimated_value":"wartość|null","execution_period":"czas realizacji|null","deposit_required":"wadium|null","participation_conditions":["warunki udziału firmy: finanse, doświadczenie — BEZ art.108/109 PZP"],"evaluation_criteria":["kryterium z wagą"],"eu_funding":"nazwa programu UE|null","risks_and_flags":["realne ryzyka — BEZ art.108/109 PZP"]}}

META: {order_object or ""} | {organization_name or ""} | CPV: {cpv_code or ""} | termin: {submitting_offers_date or ""}

{content_section}
"""
    return system, user
    return system, user
    return system, user


# =========================
# Backend: Ollama (tradycyjny)
# =========================

def summarize_with_ollama(
    model: str | None = None,
    host: str | None = None,
    **kwargs,
) -> TenderSummary:
    """
    Streszczanie przez tradycyjny Ollama (lokalny lub cloud).

    Modele cloud pobierasz normalnie:
        ollama pull kimi-k2.5:cloud
        ollama pull qwen3:32b

    Host = http://localhost:11434 (domyślnie) lub dowolny remote.
    """
    if OllamaClient is None:
        raise RuntimeError(
            "Brak biblioteki ollama. Zainstaluj: pip install ollama"
        )

    _model = model or OLLAMA_MODEL
    _host = host or OLLAMA_HOST
    _api_key = os.getenv("OLLAMA_API_KEY", "") or OLLAMA_API_KEY

    system, user = build_prompt(
        kwargs.get("order_object"),
        kwargs.get("organization_name"),
        kwargs.get("cpv_code"),
        kwargs.get("submitting_offers_date"),
        kwargs.get("html_body") or "",
    )

    # API key → Bearer header (wymagany dla cloud modeli)
    headers = {}
    if _api_key:
        headers["Authorization"] = f"Bearer {_api_key}"

    client = OllamaClient(host=_host, headers=headers)
    resp = client.chat(
        model=_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        options={"temperature": 0.2},
    )

    out_text = resp["message"]["content"]
    print(f"    📝 Odpowiedź: {len(out_text)} zn., "
          f"zawiera '{{': {'tak' if '{' in out_text else 'NIE!'}")
    # Debug: pokaż początek i koniec
    if len(out_text) > 200:
        print(f"    >>> START: {out_text[:150]!r}")
        print(f"    >>> END:   {out_text[-150:]!r}")
    else:
        print(f"    >>> FULL: {out_text!r}")
    data = extract_json(out_text)
    return TenderSummary.model_validate(data)


# =========================
# Backend: Gemini
# =========================

def summarize_with_gemini(
    model: str | None = None,
    api_key: str | None = None,
    **kwargs,
) -> TenderSummary:
    _api_key = api_key or GOOGLE_API_KEY
    if not _api_key:
        raise RuntimeError("Brak GOOGLE_API_KEY w środowisku.")
    if genai is None:
        raise RuntimeError(
            "Brak biblioteki google-genai. "
            "Zainstaluj: pip install google-genai"
        )

    _model = model or GEMINI_MODEL

    system, user = build_prompt(
        kwargs.get("order_object"),
        kwargs.get("organization_name"),
        kwargs.get("cpv_code"),
        kwargs.get("submitting_offers_date"),
        kwargs.get("html_body") or "",
    )

    client = genai.Client(api_key=_api_key)
    resp = client.models.generate_content(
        model=_model,
        contents=system + "\n\n" + user,
    )

    out_text = getattr(resp, "text", None) or str(resp)
    print(f"    📝 Odpowiedź: {len(out_text)} zn., "
          f"zawiera '{{': {'tak' if '{' in out_text else 'NIE!'}")
    data = extract_json(out_text)
    return TenderSummary.model_validate(data)


# =========================
# Dispatcher
# =========================

BACKENDS = {
    "ollama": summarize_with_ollama,
    "gemini": summarize_with_gemini,
}


def summarize_from_html(
    *,
    order_object: str | None,
    organization_name: str | None,
    cpv_code: str | None,
    submitting_offers_date: str | None,
    html_body: str,
    backend: str | None = None,
) -> TenderSummary:
    """
    Główna funkcja streszczania.

    backend: "ollama" | "gemini" (domyślnie z env TENDERBOT_LLM_BACKEND)
    """
    chosen = (backend or LLM_BACKEND).lower().strip()
    fn = BACKENDS.get(chosen)
    if fn is None:
        raise ValueError(
            f"Nieznany backend: {chosen!r}. "
            f"Dostępne: {', '.join(BACKENDS.keys())}"
        )

    return fn(
        order_object=order_object,
        organization_name=organization_name,
        cpv_code=cpv_code,
        submitting_offers_date=submitting_offers_date,
        html_body=html_body,
    )


# =========================
# Streszczenie szczegółowe (wolny tekst)
# =========================

_DETAILED_SYSTEM = (
    "Jesteś analitykiem zamówień publicznych. "
    "Streść poniższe ogłoszenie przetargowe po polsku. "
    "Wypisz WSZYSTKIE kluczowe informacje: "
    "przedmiot zamówienia, podział na części/loty, "
    "szacunkowa wartość, terminy (składanie ofert, realizacja), "
    "wadium i zabezpieczenie, "
    "warunki udziału (zdolność finansowa, doświadczenie, kadra), "
    "kryteria oceny ofert z wagami, "
    "źródło finansowania (fundusze UE?), "
    "wyłączenia i ryzyka, prawo opcji, podwykonawstwo. "
    "Pomiń standardowe artykuły PZP (108/109) — to boilerplate. "
    "Formatuj czytelnie z nagłówkami."
)


def detailed_summary_text(
    text: str,
    backend: str | None = None,
) -> str:
    """
    Streszczenie szczegółowe — wolny tekst (bez schematu JSON).
    Używa pełnego XML ogłoszenia TED.
    """
    chosen = (backend or LLM_BACKEND).lower().strip()
    content = text[:30000]

    if chosen == "ollama":
        if OllamaClient is None:
            raise RuntimeError("Brak biblioteki ollama.")
        _host = os.getenv("OLLAMA_HOST", "") or OLLAMA_HOST
        _model = os.getenv("OLLAMA_MODEL", "") or OLLAMA_MODEL
        _api_key = os.getenv("OLLAMA_API_KEY", "") or OLLAMA_API_KEY
        headers = {}
        if _api_key:
            headers["Authorization"] = f"Bearer {_api_key}"
        client = OllamaClient(host=_host, headers=headers)
        resp = client.chat(
            model=_model,
            messages=[
                {"role": "system", "content": _DETAILED_SYSTEM},
                {"role": "user", "content": content},
            ],
            options={"temperature": 0.2},
        )
        out = resp["message"]["content"]
        # Strip thinking tags
        out = re.sub(r"<think>[\s\S]*?</think>", "", out).strip()
        out = re.sub(r"<think>[\s\S]*", "", out).strip()
        return out

    elif chosen == "gemini":
        if genai is None:
            raise RuntimeError("Brak biblioteki google-genai.")
        _api_key = os.getenv("GOOGLE_API_KEY", "") or GOOGLE_API_KEY
        _model = os.getenv("GEMINI_MODEL", "") or GEMINI_MODEL
        client = genai.Client(api_key=_api_key)
        resp = client.models.generate_content(
            model=_model,
            contents=_DETAILED_SYSTEM + "\n\n" + content,
        )
        return getattr(resp, "text", None) or str(resp)

    else:
        raise ValueError(f"Nieznany backend: {chosen!r}")
