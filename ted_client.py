# ted_client.py
"""
Klient TED Search API v3 — ogłoszenia unijne (powyżej progów UE).

Endpoint: POST https://api.ted.europa.eu/v3/notices/search
Dokumentacja: https://ted.europa.eu/api/documentation/index.html

Nie wymaga API key dla wyszukiwania opublikowanych ogłoszeń.

Poprawna składnia expert query:
  buyer-country=POL AND classification-cpv IN (72000000)
  classification-cpv IN (71000000) AND publication-date>=20260101

Struktura odpowiedzi:
  { "notices": [ { "publication-number": "103647-2026", ... } ],
    "iterationNextToken": "..." }

Pola w odpowiedzi mają różne typy:
  - buyer-name: {"pol": ["nazwa"]}  (dict z listą po języku)
  - classification-cpv: ["72000000", "48000000", ...]  (lista kodów)
  - deadline-receipt-tender-date-lot: ["2026-02-26+01:00", ...]  (lista per lot)
  - publication-number: "103647-2026"  (string)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import httpx

TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

# Mapowanie polskich województw (Board/Search) → kody NUTS2 (TED)
PROVINCE_TO_NUTS = {
    "PL02": "PL51",  # dolnośląskie
    "PL04": "PL61",  # kujawsko-pomorskie
    "PL06": "PL81",  # lubelskie
    "PL08": "PL43",  # lubuskie
    "PL10": "PL71",  # łódzkie
    "PL12": "PL21",  # małopolskie
    "PL14": "PL91",  # mazowieckie (PL91+PL92)
    "PL16": "PL52",  # opolskie
    "PL18": "PL82",  # podkarpackie
    "PL20": "PL84",  # podlaskie
    "PL22": "PL63",  # pomorskie
    "PL24": "PL22",  # śląskie
    "PL26": "PL72",  # świętokrzyskie
    "PL28": "PL62",  # warmińsko-mazurskie
    "PL30": "PL41",  # wielkopolskie
    "PL32": "PL42",  # zachodniopomorskie
}
# Mazowieckie ma dwa NUTS2 — dodajemy oba
_PROVINCE_NUTS_EXTRA = {"PL14": ["PL91", "PL92"]}


def provinces_to_nuts(provinces: List[str]) -> List[str]:
    """Konwertuje kody województw na NUTS2 do filtra TED."""
    nuts: List[str] = []
    for prov in provinces:
        if prov in _PROVINCE_NUTS_EXTRA:
            nuts.extend(_PROVINCE_NUTS_EXTRA[prov])
        elif prov in PROVINCE_TO_NUTS:
            nuts.append(PROVINCE_TO_NUTS[prov])
    return nuts


# Pola do pobrania z TED API
TED_FIELDS = [
    "publication-number",
    "notice-title",
    "classification-cpv",
    "buyer-name",
    "buyer-city",
    "buyer-country",
    "publication-date",
    "notice-type",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-request-date-lot",
    "place-of-performance",
    "contract-nature",
]


@dataclass
class TedQuery:
    """Parametry wyszukiwania w TED."""

    cpv_codes: List[str] = field(default_factory=list)
    countries: List[str] = field(default_factory=lambda: ["POL"])
    nuts_codes: List[str] = field(default_factory=list)
    contract_natures: List[str] = field(
        default_factory=list
    )  # ["services", "supplies", ...]
    publication_from: Optional[datetime] = None
    publication_to: Optional[datetime] = None
    notice_types: List[str] = field(
        default_factory=lambda: ["cn-standard", "cn-social"]
    )
    limit: int = 100


# Mapowanie Board/Search OrderType → TED contract-nature
ORDER_TYPE_TO_CONTRACT_NATURE = {
    "Services": "services",
    "Supplies": "supplies",
    "Works": "works",
}


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _cpv_to_ted(cpv_prefixes: List[str]) -> List[str]:
    """
    Przygotowuje kody CPV do TED expert search.
    TED robi hierarchiczny match — classification-cpv IN (72000000)
    znajdzie też 72253200.
    Deduplikacja: najkrótszy prefix pokrywa dłuższe.
    """
    codes = []
    for cpv in cpv_prefixes:
        d = re.sub(r"\D", "", cpv).strip()
        if d:
            codes.append(d)

    codes.sort(key=len)
    result: List[str] = []
    for c in codes:
        prefix = c.rstrip("0") or c[:1]
        covered = any(
            c.startswith(existing.rstrip("0") or existing[:1]) for existing in result
        )
        if not covered:
            result.append(c)

    return result


def build_expert_query(q: TedQuery) -> str:
    """
    Buduje query w formacie TED Expert Search.

    Przykład:
      buyer-country=POL AND classification-cpv IN (72000000 48000000)
      AND publication-date>=20260213
      AND (notice-type=cn-standard OR notice-type=cn-social)
    """
    parts: List[str] = []

    # Kraje — buyer-country IN (POL DEU CZE)
    if q.countries:
        if len(q.countries) == 1:
            parts.append(f"buyer-country={q.countries[0]}")
        else:
            country_list = " ".join(q.countries)
            parts.append(f"buyer-country IN ({country_list})")

    ted_cpvs = _cpv_to_ted(q.cpv_codes)
    if ted_cpvs:
        cpv_list = " ".join(ted_cpvs)
        parts.append(f"classification-cpv IN ({cpv_list})")

    # NUTS — filtr regionu (place-of-performance)
    if q.nuts_codes:
        if len(q.nuts_codes) == 1:
            parts.append(f"place-of-performance={q.nuts_codes[0]}*")
        else:
            nuts_expr = " OR ".join(f"place-of-performance={n}*" for n in q.nuts_codes)
            parts.append(f"({nuts_expr})")

    if q.publication_from:
        parts.append(f"publication-date>={_fmt_date(q.publication_from)}")
    if q.publication_to:
        parts.append(f"publication-date<={_fmt_date(q.publication_to)}")

    if q.notice_types:
        nt_parts = " OR ".join(f"notice-type={nt}" for nt in q.notice_types)
        parts.append(f"({nt_parts})" if len(q.notice_types) > 1 else nt_parts)

    # Typ zamówienia (services / supplies / works)
    if q.contract_natures:
        if len(q.contract_natures) == 1:
            parts.append(f"contract-nature={q.contract_natures[0]}")
        else:
            cn_parts = " OR ".join(f"contract-nature={cn}" for cn in q.contract_natures)
            parts.append(f"({cn_parts})")

    return " AND ".join(parts)


def _build_request_body(
    query_str: str,
    limit: int = 100,
    iteration_token: Optional[str] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "query": query_str,
        "fields": TED_FIELDS,
        "limit": str(limit),
        "scope": "ACTIVE",
        "checkQuerySyntax": False,
        "paginationMode": "ITERATION",
    }
    if iteration_token:
        body["iterationNextToken"] = iteration_token
    return body


def fetch_ted_page(
    client: httpx.Client,
    query_str: str,
    limit: int = 100,
    iteration_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Wykonuje pojedyncze zapytanie do TED Search API."""
    body = _build_request_body(query_str, limit, iteration_token)
    r = client.post(TED_SEARCH_URL, json=body, timeout=60)
    r.raise_for_status()
    return r.json()


def iter_ted_notices(
    client: httpx.Client,
    q: TedQuery,
    max_pages: int = 50,
) -> Iterable[Dict[str, Any]]:
    """Iteruje po wynikach TED Search API z paginacją (ITERATION mode)."""
    query_str = build_expert_query(q)
    iteration_token = None

    for _ in range(max_pages):
        try:
            data = fetch_ted_page(
                client,
                query_str,
                limit=q.limit,
                iteration_token=iteration_token,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 500, 502, 503):
                time.sleep(2)
                continue
            raise

        # TED zwraca "notices" (nie "results")
        notices = data.get("notices", [])
        if not notices:
            break

        yield from notices

        iteration_token = data.get("iterationNextToken")
        if not iteration_token:
            break


# ---------------------
# Ekstrakcja pól TED
# ---------------------


def _extract_multilang(field_data: Any) -> str:
    """
    Wyciąga tekst z pola wielojęzycznego TED.

    Formaty:
      {"pol": ["tekst1", "tekst2"]}
      {"pol": "tekst"}
      "tekst"
      ["tekst1", "tekst2"]
    """
    if field_data is None:
        return ""
    if isinstance(field_data, str):
        return field_data
    if isinstance(field_data, list):
        return "; ".join(str(x) for x in field_data if x)
    if isinstance(field_data, dict):
        # Priorytet: pol > eng > pierwszy dostępny
        for lang in ("pol", "POL", "eng", "ENG"):
            if lang in field_data:
                val = field_data[lang]
                if isinstance(val, list):
                    return "; ".join(str(x) for x in val if x)
                return str(val)
        # Pierwszy dostępny
        for val in field_data.values():
            if isinstance(val, list):
                return "; ".join(str(x) for x in val if x)
            if val:
                return str(val)
    return str(field_data) if field_data else ""


def _extract_cpv_list(field_data: Any) -> str:
    """
    Konwertuje listę kodów CPV na string format zbliżony do Board/Search.
    TED zwraca: ["72000000", "48000000", ...]
    Wynik: "72000000, 48000000, ..."
    """
    if field_data is None:
        return ""
    if isinstance(field_data, list):
        # Unikalne kody, zachowaj kolejność
        seen = set()
        unique = []
        for code in field_data:
            s = str(code).strip()
            if s and s not in seen:
                seen.add(s)
                unique.append(s)
        return ", ".join(unique)
    return str(field_data)


def _extract_first_date(field_data: Any) -> str:
    """
    Wyciąga najwcześniejszy deadline z listy dat per lot.
    TED zwraca: ["2026-02-26+01:00", "2026-02-26+01:00", ...]
    """
    if field_data is None:
        return ""
    if isinstance(field_data, str):
        return field_data
    if isinstance(field_data, list) and field_data:
        # Zwróć najwcześniejszą datę (sortuj leksykograficznie)
        dates = sorted(str(d) for d in field_data if d)
        return dates[0] if dates else ""
    return str(field_data) if field_data else ""


def normalize_ted_notice(ted_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizuje ogłoszenie TED do formatu zbliżonego do Board/Search,
    żeby można go było zapisać w tej samej tabeli notices.
    """
    pub_number = ted_item.get("publication-number", "")
    if isinstance(pub_number, list):
        pub_number = pub_number[0] if pub_number else ""

    return {
        "objectId": f"ted-{pub_number}" if pub_number else None,
        "noticeType": "TED-" + (ted_item.get("notice-type") or ""),
        "noticeNumber": pub_number,
        "bzpNumber": None,
        "isTenderAmountBelowEU": False,
        "publicationDate": _extract_first_date(ted_item.get("publication-date")),
        "orderObject": _extract_multilang(ted_item.get("notice-title")),
        "cpvCode": _extract_cpv_list(ted_item.get("classification-cpv")),
        "submittingOffersDate": (
            _extract_first_date(ted_item.get("deadline-receipt-tender-date-lot"))
            or _extract_first_date(ted_item.get("deadline-receipt-request-date-lot"))
        ),
        "organizationName": _extract_multilang(ted_item.get("buyer-name")),
        "organizationCity": _extract_multilang(ted_item.get("buyer-city")),
        "organizationProvince": None,
        "organizationCountry": _extract_multilang(ted_item.get("buyer-country")),
        "htmlBody": None,
        "tenderId": None,
        "tenderType": {
            "services": "Services",
            "supplies": "Supplies",
            "works": "Works",
        }.get(((ted_item.get("contract-nature") or [""])[0]).lower()),
        "orderType": None,
        "_source": "TED",
        "_ted_pub_number": pub_number,
    }


# =====================
# TED XML — pełna treść ogłoszenia
# =====================

TED_XML_URL = "https://ted.europa.eu/en/notice/{pub_number}/xml"

# Namespacey eForms XML
_XML_NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "efac": "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1",
    "efbc": "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1",
}


def fetch_ted_xml(
    pub_number: str, client: Optional[httpx.Client] = None
) -> Optional[str]:
    """
    Pobiera XML ogłoszenia z TED.
    Zwraca surowy XML jako string lub None przy błędzie.
    """
    url = TED_XML_URL.format(pub_number=pub_number)
    try:
        if client:
            r = client.get(url, timeout=30, follow_redirects=True)
        else:
            r = httpx.get(url, timeout=30, follow_redirects=True)
        if r.status_code == 200 and r.text.strip().startswith("<?xml"):
            return r.text
    except Exception:
        pass
    return None


def extract_text_from_ted_xml(xml_text: str, lang: str = "POL") -> str:
    """
    Wyciąga kluczowe tagi z XML eForms ogłoszenia TED.

    Zbiera:
      ✅ ProcurementProject > Name/Description → nazwa i opis
      ✅ AwardingCriterion > Description → kryteria oceny
      ✅ efac:Funding > Description → finansowanie UE
      ✅ TendererQualificationRequest > Description → warunki udziału
         (tylko merytoryczne: "Warunek zostanie...", nie art. 108/109)
      ✅ DurationMeasure → czas realizacji
      ✅ GuaranteeTypeCode → wadium tak/nie
      ✅ Note (krótkie) → zabezpieczenie
      ✅ TenderingProcess > Description → tryb

    Pomijane:
      ❌ RequiredFinancialGuarantee Description (szczegóły wadium per lot)
      ❌ AppealTerms (środki odwoławcze — identyczne)
      ❌ OpenTenderEvent (URL platformy)
      ❌ Długie Note (JEDZ, dokumenty)
      ❌ Art. 108/109 PZP (boilerplate wykluczeniowy)
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return ""

    def _pol(elem) -> str:
        if elem is not None and elem.get("languageID") == lang and elem.text:
            return elem.text.strip()
        return ""

    sections: List[str] = []
    seen: set[str] = set()

    def _add(label: str, text: str) -> None:
        if text and text[:80] not in seen:
            seen.add(text[:80])
            sections.append(f"{label}: {text}" if label else text)

    # Szum proceduralny
    _NOISE_STARTS = (
        "oświadczeni",
        "wykonawca dołącza",
        "oferta składana",
        "wykonawcom, a także",
        "odwołanie wnosi",
    )

    def _is_noise(text: str) -> bool:
        low = text[:60].lower().strip()
        return any(low.startswith(n) for n in _NOISE_STARTS)

    # 1. Główny projekt — nazwa i opis
    for proj in root.findall(".//cac:ProcurementProject", _XML_NS):
        name = proj.find("cbc:Name", _XML_NS)
        desc = proj.find("cbc:Description", _XML_NS)
        _add("PROJEKT", _pol(name))
        desc_text = _pol(desc)
        if desc_text and not _is_noise(desc_text):
            _add("OPIS", desc_text)

    # 2. Loty — nazwa, opis, czas realizacji
    for lot in root.findall(".//cac:ProcurementProjectLot", _XML_NS):
        lot_id_el = lot.find("cbc:ID", _XML_NS)
        lot_id = lot_id_el.text if lot_id_el is not None else "?"
        proj = lot.find("cac:ProcurementProject", _XML_NS)
        if proj is not None:
            name = proj.find("cbc:Name", _XML_NS)
            desc = proj.find("cbc:Description", _XML_NS)
            _add(f"LOT {lot_id}", _pol(name))
            desc_text = _pol(desc)
            if desc_text and not _is_noise(desc_text):
                _add("OPIS", desc_text)

        # Czas realizacji
        dur = lot.find(".//cac:PlannedPeriod/cbc:DurationMeasure", _XML_NS)
        if dur is not None and dur.text:
            unit = dur.get("unitCode", "")
            unit_pl = {"DAY": "dni", "MONTH": "miesięcy", "YEAR": "lat"}.get(unit, unit)
            _add("REALIZACJA", f"{dur.text} {unit_pl}")

        # 3. Kryteria oceny (deduplikacja)
        for award in lot.findall(".//cac:AwardingTerms//cbc:Description", _XML_NS):
            text = _pol(award)
            if not text:
                continue
            norm = re.sub(r"części\s+\d+", "części N", text[:80])
            if norm not in seen:
                seen.add(norm)
                sections.append(f"KRYTERIA ({lot_id}): {text}")

        # 4. Finansowanie UE
        for funding in lot.findall(".//efac:Funding/cbc:Description", _XML_NS):
            _add("FINANSOWANIE", _pol(funding))

    # 5. Warunki udziału — MERYTORYCZNE (nie art. 108/109 PZP)
    for qual_desc in root.findall(
        ".//cac:TendererQualificationRequest//cbc:Description", _XML_NS
    ):
        text = _pol(qual_desc)
        if not text:
            continue
        low = text[:60].lower()
        # Przepuść: warunki z konkretnymi progami
        if any(
            kw in low
            for kw in (
                "warunek zostanie",
                "zdolność",
                "doświadczeni",
                "wykaz",
                "środkami finansow",
                "ubezpieczeni",
                "potencjał",
                "kwalifikacj",
                "uprawni",
            )
        ):
            _add("WARUNEK UDZIAŁU", text)
        # Pomiń: standardowe artykuły PZP (108/109)

    # 6. Note — krótkie (zabezpieczenie, wadium)
    for note in root.findall(".//cbc:Note", _XML_NS):
        text = _pol(note)
        if text and len(text) < 500 and not _is_noise(text):
            _add("UWAGA", text)

    # 7. Wadium
    guarantee_codes = set()
    for guar in root.findall(".//cac:RequiredFinancialGuarantee", _XML_NS):
        code = guar.find("cbc:GuaranteeTypeCode", _XML_NS)
        if code is not None:
            guarantee_codes.add(code.text)
    if "true" in guarantee_codes:
        _add("WADIUM", "wymagane")
    elif "false" in guarantee_codes:
        _add("WADIUM", "nie wymagane")

    # 8. Tryb postępowania
    for tp in root.findall(".//cac:TenderingProcess/cbc:Description", _XML_NS):
        _add("TRYB", _pol(tp))

    return "\n\n".join(sections)
