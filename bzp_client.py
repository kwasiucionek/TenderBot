# bzp_client.py
"""
Klient API e-Zamówienia oparty o oficjalny endpoint /mo-board/api/v1/notice.

Oficjalne API (opisane w Instrukcji integracji z API BZP) zwraca pełną treść
ogłoszenia w polu htmlBody — bez potrzeby scrapowania Angular SPA.

Paginacja: SearchAfter (kursor = objectId ostatniego wyniku)
PageSize: max 500
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import httpx

NOTICE_URL = "https://ezamowienia.gov.pl/mo-board/api/v1/notice"


@dataclass(frozen=True)
class BzpQuery:
    publication_from: datetime = None
    publication_to: Optional[datetime] = None
    page_size: int = 500

    # Filtry opcjonalne:
    notice_type: Optional[str] = None      # domyślnie ContractNotice
    order_type: Optional[str] = None       # Delivery / Services / Works
    cpv_code: Optional[str] = None
    organization_province: Optional[str] = None
    organization_name: Optional[str] = None
    is_below_eu: Optional[bool] = None    # True=krajowe, False=unijne, None=oba


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def build_params(q: BzpQuery, search_after: str = "") -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "NoticeType": q.notice_type or "ContractNotice",
        "PublicationDateFrom": _fmt_dt(q.publication_from),
        "PublicationDateTo": _fmt_dt(q.publication_to) if q.publication_to else _fmt_dt(datetime.utcnow()),
        "PageSize": q.page_size,
    }
    if search_after:
        params["SearchAfter"] = search_after
    if q.order_type:
        params["OrderType"] = q.order_type
    if q.cpv_code:
        params["CpvCode"] = q.cpv_code
    if q.organization_province:
        params["OrganizationProvince"] = q.organization_province
    if q.organization_name:
        params["OrganizationName"] = q.organization_name
    return params


def fetch_page(
    client: httpx.Client, q: BzpQuery, search_after: str = ""
) -> List[Dict[str, Any]]:
    params = build_params(q, search_after)
    headers = {"Accept": "application/json"}
    r = client.get(NOTICE_URL, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected response type: {type(data)}")
    return data


def iter_notices(
    client: httpx.Client, q: BzpQuery, max_pages: int = 500
) -> Iterable[Dict[str, Any]]:
    """
    Iteruje przez ogłoszenia używając paginacji SearchAfter (kursor).
    Każde ogłoszenie zawiera pełne htmlBody.
    """
    search_after = ""
    for _ in range(max_pages):
        results = fetch_page(client, q, search_after=search_after)
        if not results:
            break
        for item in results:
            if "objectId" not in item:
                continue
            yield item
        if len(results) < q.page_size:
            break
        search_after = results[-1].get("objectId", "")
        if not search_after:
            break


def fetch_notice_html(
    object_id: str,
    client: Optional[httpx.Client] = None,
    bzp_number: Optional[str] = None,
    notice_number: Optional[str] = None,
) -> str:
    """
    Pobiera treść ogłoszenia BZP przez oficjalne API.

    Strategie (w kolejności):
    1. Szukaj po NoticeNumber (bzpNumber lub noticeNumber z bazy)
    2. Szukaj po ObjectId w ogłoszeniach z ostatnich 90 dni (SearchAfter)
    Zwraca htmlBody lub pusty string.
    """
    headers = {"Accept": "application/json"}
    now = datetime.utcnow()
    date_from = (now - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00")
    date_to = now.strftime("%Y-%m-%dT23:59:59")

    def _search(params) -> str:
        try:
            if client:
                r = client.get(NOTICE_URL, params=params, headers=headers, timeout=30)
            else:
                r = httpx.get(NOTICE_URL, params=params, headers=headers, timeout=30)
            if r.status_code != 200:
                return ""
            data = r.json()
            if not isinstance(data, list):
                return ""
            for item in data:
                if item.get("objectId") == object_id:
                    return item.get("htmlBody") or ""
            # Jeśli tylko 1 wynik i brak lepszej opcji — zwróć go
            if len(data) == 1 and data[0].get("htmlBody"):
                return data[0]["htmlBody"]
        except Exception:
            pass
        return ""

    # Strategia 1: szukaj po numerze ogłoszenia (najbardziej precyzyjne)
    for num in filter(None, [bzp_number, notice_number]):
        for notice_type in ("ContractNotice", "TenderResultNotice",
                            "NoticeUpdateNotice", "SmallContractNotice"):
            result = _search({
                "NoticeType": notice_type,
                "NoticeNumber": num,
                "PublicationDateFrom": date_from,
                "PublicationDateTo": date_to,
                "PageSize": 10,
            })
            if result:
                return result

    # Strategia 2: przeszukaj po objectId jako SearchAfter + 1 strona wstecz
    for notice_type in ("ContractNotice", "TenderResultNotice",
                        "NoticeUpdateNotice", "SmallContractNotice"):
        result = _search({
            "NoticeType": notice_type,
            "PublicationDateFrom": date_from,
            "PublicationDateTo": date_to,
            "PageSize": 500,
            "SearchAfter": object_id,
        })
        if result:
            return result

    return ""


def extract_bzp_text(html: str) -> str:
    """
    Wyciąga czytelny tekst z htmlBody ogłoszenia BZP.
    """
    import re as _re

    text = _re.sub(r"<script[\s\S]*?</script>", " ", html, flags=_re.I)
    text = _re.sub(r"<style[\s\S]*?</style>", " ", text, flags=_re.I)
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"\s+", " ", text).strip()

    idx = text.find("SEKCJA I")
    if idx > 0:
        text = text[idx:]

    return text
