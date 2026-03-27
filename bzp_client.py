# bzp_client.py
"""
Klient API e-Zamówienia oparty o endpoint /api/v1/Board/Search.

Ten endpoint (używany przez frontend ezamowienia.gov.pl) zwraca WSZYSTKIE
ogłoszenia — zarówno krajowe (BZP) jak i unijne (TED/eForms).

Paginacja: PageNumber + PageSize (max 100 wg obserwacji)
Sortowanie: SortingColumnName + SortingDirection
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import httpx

SEARCH_URL = (
    "https://ezamowienia.gov.pl/mo-board/api/v1/Board/Search"
)


@dataclass(frozen=True)
class BzpQuery:
    publication_from: datetime = None
    publication_to: Optional[datetime] = None
    page_size: int = 100

    # Filtry opcjonalne:
    notice_type: Optional[str] = None
    order_type: Optional[str] = None
    cpv_code: Optional[str] = None
    organization_province: Optional[str] = None
    organization_name: Optional[str] = None
    is_below_eu: Optional[bool] = None   # True=krajowe, False=unijne, None=oba


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def build_params(q: BzpQuery, page_number: int = 1) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "publicationDateFrom": _fmt_dt(q.publication_from),
        "SortingColumnName": "PublicationDate",
        "SortingDirection": "DESC",
        "PageNumber": page_number,
        "PageSize": q.page_size,
    }
    if q.publication_to:
        params["publicationDateTo"] = _fmt_dt(q.publication_to)
    if q.notice_type:
        params["NoticeType"] = q.notice_type
    if q.order_type:
        params["OrderType"] = q.order_type
    if q.cpv_code:
        params["CpvCode"] = q.cpv_code
    if q.organization_province:
        params["OrganizationProvince"] = q.organization_province
    if q.organization_name:
        params["OrganizationName"] = q.organization_name
    if q.is_below_eu is not None:
        params["IsTenderAmountBelowEU"] = str(q.is_below_eu).lower()
    return params


def fetch_page(
    client: httpx.Client, q: BzpQuery, page_number: int = 1
) -> List[Dict[str, Any]]:
    params = build_params(q, page_number)
    r = client.get(SEARCH_URL, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected response type: {type(data)}")
    return data


def iter_notices(
    client: httpx.Client, q: BzpQuery, max_pages: int = 500
) -> Iterable[Dict[str, Any]]:
    for page in range(1, max_pages + 1):
        results = fetch_page(client, q, page_number=page)
        if not results:
            break
        for item in results:
            yield item
        if len(results) < q.page_size:
            break


def fetch_notice_html(
    object_id: str,
    client: Optional[httpx.Client] = None,
) -> str:
    """
    Pobiera treść ogłoszenia BZP.

    Strategia: pobiera stronę frontendu ezamowienia.gov.pl
    (Angular SSR — treść jest w HTML bez JavaScript).

    Zwraca surowy HTML lub pusty string.
    """
    url = (
        f"https://ezamowienia.gov.pl/mo-client-board/bzp/"
        f"notice-details/id/{object_id}"
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl,en;q=0.5",
    }
    try:
        if client:
            r = client.get(url, timeout=30, headers=headers, follow_redirects=True)
        else:
            r = httpx.get(url, timeout=30, headers=headers, follow_redirects=True)
        if r.status_code == 200 and "SEKCJA" in r.text:
            return r.text
    except Exception:
        pass
    return ""


def extract_bzp_text(html: str) -> str:
    """
    Wyciąga czytelny tekst z HTML strony ogłoszenia BZP.

    Strona ezamowienia.gov.pl to Angular SSR — treść ogłoszenia
    jest w HTML od 'SEKCJA I' do końca, otoczona nagłówkami h2/h3.

    Strip HTML tagi i wycina od 'SEKCJA I' (pomijając
    nawigację, CSS, header strony).
    """
    import re as _re

    # Strip script/style
    text = _re.sub(r"<script[\s\S]*?</script>", " ", html, flags=_re.I)
    text = _re.sub(r"<style[\s\S]*?</style>", " ", text, flags=_re.I)
    # Strip HTML tags
    text = _re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = _re.sub(r"\s+", " ", text).strip()

    # Wytnij od SEKCJA I (pomiń header Angular)
    idx = text.find("SEKCJA I")
    if idx > 0:
        text = text[idx:]

    return text
