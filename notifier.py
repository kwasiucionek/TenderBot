#!/usr/bin/env python3
# notifier.py
"""
TenderBot — codzienny digest emailowy.

Wysyła email ze streszczeniem nowych ogłoszeń z ostatnich N godzin.

Zmienne środowiskowe (wymagane):
  TENDERBOT_SMTP_HOST       — serwer SMTP, np. smtp.gmail.com
  TENDERBOT_SMTP_PORT       — port, domyślnie 587
  TENDERBOT_SMTP_USER       — login SMTP (adres email nadawcy)
  TENDERBOT_SMTP_PASSWORD   — hasło / app password
  TENDERBOT_EMAIL_TO        — odbiorca (można podać kilka, oddzielone przecinkiem)

Zmienne opcjonalne:
  TENDERBOT_DB              — ścieżka do bazy, domyślnie data/tenderbot.sqlite
  TENDERBOT_DIGEST_HOURS    — ile godzin wstecz szukać nowych ogłoszeń, domyślnie 25
  TENDERBOT_APP_URL         — URL aplikacji Streamlit, np. https://tenderbot.cytr.us

Uruchomienie jako cron (np. codziennie o 8:00):
  0 8 * * * cd /home/kwasiucionek/TenderBot && \
    TENDERBOT_SMTP_HOST=smtp.gmail.com \
    TENDERBOT_SMTP_USER=you@gmail.com \
    TENDERBOT_SMTP_PASSWORD=apppassword \
    TENDERBOT_EMAIL_TO=you@gmail.com \
    /home/kwasiucionek/miniconda3/bin/python3 notifier.py >> logs/notifier.log 2>&1
"""
from __future__ import annotations

import json
import os
import shutil
import smtplib
import sqlite3
import subprocess
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

DB_PATH      = os.getenv("TENDERBOT_DB", "data/tenderbot.sqlite")
SMTP_HOST    = os.getenv("TENDERBOT_SMTP_HOST", "")
SMTP_PORT    = int(os.getenv("TENDERBOT_SMTP_PORT", "587"))
SMTP_USER    = os.getenv("TENDERBOT_SMTP_USER", "")
SMTP_PASS    = os.getenv("TENDERBOT_SMTP_PASSWORD", "")
EMAIL_TO     = [e.strip() for e in os.getenv("TENDERBOT_EMAIL_TO", "").split(",") if e.strip()]
DIGEST_HOURS  = int(os.getenv("TENDERBOT_DIGEST_HOURS", "25"))
APP_URL       = os.getenv("TENDERBOT_APP_URL", "").rstrip("/")
ONLY_STARRED  = os.getenv("TENDERBOT_ONLY_STARRED", "0") == "1"  # 1 = tylko ⭐
USE_PUSHER   = os.getenv("TENDERBOT_USE_PUSHER", "auto")  # auto / yes / no


# ──────────────────────────────────────────────
# DB
# ──────────────────────────────────────────────

def get_new_notices(db_path: str, hours_back: int) -> List[Dict[str, Any]]:
    """Zwraca aktywne ogłoszenia dodane/zaktualizowane w ciągu ostatnich N godzin."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

    if ONLY_STARRED:
        rows = conn.execute("""
            SELECT
                n.object_id, n.order_object, n.organization_name,
                n.organization_city, n.cpv_code, n.submitting_offers_date,
                n.publication_date, n.is_below_eu, n.profile_name, n.user_status,
                json_extract(n.payload_json, '$.organizationCountry') as country,
                s.summary_json, s.detailed_text
            FROM notices n
            LEFT JOIN summaries s ON s.object_id = n.object_id
            WHERE n.user_status = 'starred'
              AND n.updated_at >= ?
            ORDER BY n.publication_date DESC
        """, (cutoff,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT
                n.object_id, n.order_object, n.organization_name,
                n.organization_city, n.cpv_code, n.submitting_offers_date,
                n.publication_date, n.is_below_eu, n.profile_name, n.user_status,
                json_extract(n.payload_json, '$.organizationCountry') as country,
                s.summary_json, s.detailed_text
            FROM notices n
            LEFT JOIN summaries s ON s.object_id = n.object_id
            WHERE (n.user_status IS NULL OR n.user_status = 'starred')
              AND n.updated_at >= ?
            ORDER BY n.user_status DESC, n.publication_date DESC
        """, (cutoff,)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# FORMATOWANIE
# ──────────────────────────────────────────────

EZ_NOTICE_URL = "https://ezamowienia.gov.pl/mo-client-board/bzp/notice-details/id/{object_id}"
TED_NOTICE_URL = "https://ted.europa.eu/en/notice/-/detail/{pub_number}"


def _notice_url(object_id: str) -> str:
    """Link bezpośrednio do ogłoszenia na BZP lub TED."""
    if object_id.startswith("ted-"):
        pub = object_id.removeprefix("ted-")
        return TED_NOTICE_URL.format(pub_number=pub)
    return EZ_NOTICE_URL.format(object_id=object_id)


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return date_str[:10] if date_str else "—"


def _short_summary(summary_json: str | None) -> str:
    """Wyciąga krótki opis z summary_json."""
    if not summary_json:
        return ""
    try:
        data = json.loads(summary_json)
        parts = []
        if data.get("scope"):
            parts.append(data["scope"])
        if data.get("key_requirements"):
            reqs = data["key_requirements"]
            if isinstance(reqs, list):
                parts.extend(reqs[:2])
            elif isinstance(reqs, str):
                parts.append(reqs)
        return " • ".join(parts[:3])
    except Exception:
        return ""


def build_html(notices: List[Dict[str, Any]], hours_back: int) -> str:
    """Buduje treść HTML emaila."""

    starred = [n for n in notices if n.get("user_status") == "starred"]
    regular = [n for n in notices if n.get("user_status") != "starred"]

    total = len(notices)
    date_str = datetime.now().strftime("%d.%m.%Y")

    def notice_block(n: Dict) -> str:
        oid = n["object_id"]
        is_ted = oid.startswith("ted-")
        source = "TED" if is_ted else "BZP"
        eu_tag = "🇪🇺 EU" if n.get("is_below_eu") == 0 else "🇵🇱 PL"
        star = "⭐ " if n.get("user_status") == "starred" else ""
        title = n.get("order_object") or "—"
        org = n.get("organization_name") or "—"
        city = n.get("organization_city") or ""
        country = n.get("country") or ""
        location = ", ".join(filter(None, [city, country if country != "POL" else ""]))
        deadline = _format_date(n.get("submitting_offers_date"))
        pub_date = _format_date(n.get("publication_date"))
        cpv = (n.get("cpv_code") or "")[:60]
        summary = _short_summary(n.get("summary_json"))
        url = _notice_url(oid)

        return f"""
        <tr>
          <td style="padding:12px 8px; border-bottom:1px solid #e5e7eb; vertical-align:top;">
            <div style="font-size:11px; color:#6b7280; margin-bottom:4px;">
              {star}{source} · {eu_tag} · opubl. {pub_date}
            </div>
            <div style="font-weight:600; font-size:14px; margin-bottom:4px;">
              <a href="{url}" style="color:#1d4ed8; text-decoration:none;">{title}</a>
            </div>
            <div style="font-size:13px; color:#374151; margin-bottom:4px;">
              🏢 {org}{f' · 📍 {location}' if location else ''}
            </div>
            {f'<div style="font-size:12px; color:#6b7280; margin-bottom:4px;">📋 {cpv}</div>' if cpv else ''}
            {f'<div style="font-size:12px; color:#4b5563; margin-bottom:4px;">{summary}</div>' if summary else ''}
            <div style="font-size:12px; color:#dc2626; font-weight:500;">
              ⏰ Deadline: {deadline}
            </div>
          </td>
        </tr>"""

    def section(title: str, items: List[Dict], bg: str = "#f9fafb") -> str:
        if not items:
            return ""
        rows = "".join(notice_block(n) for n in items)
        return f"""
        <tr><td style="padding:20px 0 8px 0;">
          <div style="font-size:16px; font-weight:700; color:#111827; border-left:4px solid #1d4ed8;
                      padding-left:10px;">{title} ({len(items)})</div>
        </td></tr>
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:{bg}; border:1px solid #e5e7eb; border-radius:8px;">
            {rows}
          </table>
        </td></tr>"""

    starred_section = section("⭐ Oznaczone", starred, "#fffbeb")
    regular_section = section("🆕 Nowe ogłoszenia", regular)

    if not starred_section and not regular_section:
        content = """
        <tr><td style="padding:40px; text-align:center; color:#6b7280; font-size:15px;">
          Brak nowych ogłoszeń w tym okresie.
        </td></tr>"""
    else:
        content = starred_section + regular_section

    app_link = f'<a href="{APP_URL}" style="color:#1d4ed8;">Otwórz TenderBot</a>' if APP_URL else "TenderBot"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:system-ui,-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6; padding:24px 0;">
    <tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0"
             style="background:#ffffff; border-radius:12px; overflow:hidden;
                    box-shadow:0 1px 3px rgba(0,0,0,.1);">

        <!-- HEADER -->
        <tr><td style="background:linear-gradient(135deg,#1d4ed8,#2563eb); padding:24px 32px;">
          <div style="color:#fff; font-size:22px; font-weight:700;">📋 TenderBot Digest</div>
          <div style="color:#bfdbfe; font-size:13px; margin-top:4px;">
            {date_str} · ostatnie {hours_back}h · {total} nowych ogłoszeń
          </div>
        </td></tr>

        <!-- CONTENT -->
        <tr><td style="padding:24px 32px;">
          <table width="100%" cellpadding="0" cellspacing="0">
            {content}
          </table>
        </td></tr>

        <!-- FOOTER -->
        <tr><td style="background:#f9fafb; padding:16px 32px; border-top:1px solid #e5e7eb;
                        text-align:center; font-size:12px; color:#9ca3af;">
          {app_link} · Wygenerowano automatycznie
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_text(notices: List[Dict[str, Any]], hours_back: int) -> str:
    """Wersja tekstowa emaila (fallback)."""
    lines = [
        f"TenderBot Digest — {datetime.now().strftime('%d.%m.%Y')}",
        f"Ostatnie {hours_back}h · {len(notices)} nowych ogłoszeń",
        "=" * 60,
        "",
    ]
    for n in notices:
        star = "⭐ " if n.get("user_status") == "starred" else ""
        source = "TED" if n["object_id"].startswith("ted-") else "BZP"
        lines.append(f"{star}[{source}] {n.get('order_object', '—')}")
        lines.append(f"  Org: {n.get('organization_name', '—')}")
        lines.append(f"  Deadline: {_format_date(n.get('submitting_offers_date'))}")
        lines.append(f"  Link: {_notice_url(n['object_id'])}")
        lines.append("")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# WYSYŁKA
# ──────────────────────────────────────────────

def _pusher_available() -> bool:
    """Sprawdza czy pusher jest dostępny na serwerze."""
    return shutil.which("pusher") is not None


def send_via_pusher(notices: List[Dict[str, Any]], hours_back: int) -> None:
    """Wysyła digest przez Mikrus pusher (curl do push.mikr.us)."""
    subject = (
        f"TenderBot_{len(notices)}_nowych_ogloszen_"
        f"{datetime.now().strftime('%d.%m.%Y')}"
    )
    text = build_text(notices, hours_back)
    print(f"📧 Wysyłam digest przez pusher ({len(notices)} ogłoszeń)...")

    # Pusher = curl --data-urlencode data@- push.mikr.us/<temat>
    result = subprocess.run(
        ["curl", "-s", "--data-urlencode", "data@-", f"push.mikr.us/{subject}"],
        input=text,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"✅ Pusher: wysłano pomyślnie")
    else:
        print(f"❌ Pusher błąd: {result.stderr or result.stdout}")
        raise RuntimeError(f"pusher failed: {result.stderr}")


def send_via_smtp(notices: List[Dict[str, Any]], hours_back: int) -> None:
    """Wysyła digest przez SMTP."""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not EMAIL_TO:
        print("❌ Brak konfiguracji SMTP — ustaw zmienne środowiskowe.")
        raise RuntimeError("Missing SMTP config")

    mode = "⭐ oznaczone" if ONLY_STARRED else "nowe"
    subject = (
        f"TenderBot: {len(notices)} {mode} ogłoszeń "
        f"({datetime.now().strftime('%d.%m.%Y')})"
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"TenderBot <{SMTP_USER}>"
    msg["To"] = ", ".join(EMAIL_TO)
    msg.attach(MIMEText(build_text(notices, hours_back), "plain", "utf-8"))
    msg.attach(MIMEText(build_html(notices, hours_back), "html", "utf-8"))

    print(f"📧 Wysyłam digest przez SMTP do: {', '.join(EMAIL_TO)}")
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    print(f"✅ SMTP: wysłano pomyślnie ({len(notices)} ogłoszeń)")


def send_digest(notices: List[Dict[str, Any]], hours_back: int) -> None:
    """Wysyła digest — automatycznie wybiera pusher lub SMTP."""
    use_pusher = USE_PUSHER.lower()
    if use_pusher == "yes" or (use_pusher == "auto" and _pusher_available()):
        send_via_pusher(notices, hours_back)
    else:
        send_via_smtp(notices, hours_back)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main() -> None:
    print(f"TenderBot Notifier — {datetime.now().isoformat()}")
    print(f"Baza: {DB_PATH}")
    print(f"Zakres: ostatnie {DIGEST_HOURS}h")

    notices = get_new_notices(DB_PATH, DIGEST_HOURS)
    mode = "oznaczonych (⭐)" if ONLY_STARRED else "nowych"
    print(f"Znaleziono {mode} ogłoszeń: {len(notices)}")

    if not notices:
        print(f"Brak {mode} ogłoszeń — email nie zostanie wysłany.")
        return

    send_digest(notices, DIGEST_HOURS)


if __name__ == "__main__":
    main()
