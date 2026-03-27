# TenderBot — Monitor Zamówień Publicznych

Monitor ogłoszeń o zamówieniach publicznych z Biuletynu Zamówień Publicznych (BZP) oraz europejskiego portalu TED, z interfejsem Streamlit i dwupoziomowymi streszczeniami AI.

## Typowy workflow

1. **▶️ Monitor** — pobiera ogłoszenia z BZP + TED do bazy
2. **🧠 Summarize** — generuje krótkie streszczenia strukturalne (batch)
3. Przeglądasz listę → filtrujesz, oznaczasz ⭐/❌, ignorujesz niechciane CPV
4. **📋 Szczegółowe** — klikasz per ogłoszenie, które Cię zainteresowało (pełne streszczenie z XML/HTML)
5. **🔗 Ogłoszenie** — otwierasz pełną treść na ezamowienia.gov.pl lub ted.europa.eu

## Funkcje

- **Dwuźródłowy monitoring** — Board/Search API (ezamowienia.gov.pl) dla polskich ogłoszeń + TED Search API v3 dla ogłoszeń unijnych z całej UE/EOG
- **Profile filtrów** — konfigurowalne kody CPV, województwa (NUTS2), kraje, słowa kluczowe
- **Dwupoziomowe streszczenia AI**:
  - **Strukturalne** (batch) — JSON z polami: zakres, loty, wartość, czas realizacji, wadium, warunki udziału, kryteria oceny, finansowanie UE, ryzyka
  - **Szczegółowe** (per ogłoszenie) — wolny tekst z pełną treścią XML/HTML, bez wymuszania schematu
- **Pobieranie XML z TED** — automatyczne pobranie i parsowanie eForms XML dla ogłoszeń unijnych (treść merytoryczna, bez boilerplate PZP)
- **Oznaczanie ogłoszeń** — ⭐ wybrane / ❌ odrzucone, z trwałym zapisem; odrzucone pomijane przy kolejnym pobraniu
- **Ignorowanie CPV** — ukrywanie niechcianych kategorii z możliwością przywrócenia
- **Filtrowanie** — procedura, status (otwarte/zakończone — obliczane na żywo), keywords, profil, oznaczenie, wyszukiwarka
- **Live logi** — postęp monitora i streszczeń w czasie rzeczywistym w sidebarze
- **Backend LLM** — Ollama (lokalne/cloud) lub Google Gemini, konfigurowalny z UI

## Struktura projektu

```
tenderbot/
├── app.py              # Panel Streamlit (UI)
├── monitor.py          # Pobieranie ogłoszeń z BZP + TED
├── summarize.py        # Batch streszczenia strukturalne
├── ai_agent.py         # Backend LLM (Ollama / Gemini) + streszczenia szczegółowe
├── bzp_client.py       # Klient API Board/Search (ezamowienia.gov.pl)
├── ted_client.py       # Klient TED Search API v3 + parser XML eForms
├── storage.py          # Warstwa dostępu do bazy danych
├── cpv_2008_ver_2013.csv  # Słownik kodów CPV (wymagany)
└── data/
    └── tenderbot.sqlite   # Baza SQLite (tworzona automatycznie)
```

## Wymagania

- Python 3.11+
- Ollama (lokalnie lub remote) — do streszczeń AI

### Zależności Python

```bash
pip install streamlit pandas httpx pydantic ollama
# Opcjonalnie (backend Gemini):
pip install google-genai
```

### Plik CPV

Pobierz słownik kodów CPV i umieść obok `app.py`:
- Plik: `cpv_2008_ver_2013.csv`
- Kolumny: `CODE`, `PL` (kod 8-cyfrowy, opis po polsku)

## Uruchomienie

```bash
cd tenderbot/
streamlit run app.py
```

Aplikacja otworzy się na `http://localhost:8501`.

## Zmienne środowiskowe

| Zmienna | Domyślna wartość | Opis |
|---|---|---|
| `TENDERBOT_DB` | `data/tenderbot.sqlite` | Ścieżka do bazy SQLite |
| `TENDERBOT_HOURS_BACK` | `168` | Ile godzin wstecz szukać ogłoszeń |
| `TENDERBOT_PAGE_SIZE` | `100` | Rozmiar strony API Board/Search |
| `TENDERBOT_SKIP_TED` | `0` | `1` = pomiń TED API |
| `TENDERBOT_DEBUG` | `0` | `1` = szczegółowe logi |
| `TENDERBOT_LLM_BACKEND` | `ollama` | Backend AI: `ollama` lub `gemini` |
| `TENDERBOT_SUMMARY_BATCH` | `10` | Ile ogłoszeń streszczać w jednym uruchomieniu |
| `OLLAMA_HOST` | `http://localhost:11434` | Adres serwera Ollama |
| `OLLAMA_MODEL` | `kimi-k2.5:cloud` | Model Ollama do streszczeń |
| `OLLAMA_API_KEY` | *(puste)* | Klucz API Ollama (dla cloud) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model Gemini do streszczeń |
| `GOOGLE_API_KEY` | *(puste)* | Klucz API Google Gemini |

## Źródła danych

### Board/Search API (ezamowienia.gov.pl)
- Ogłoszenia krajowe (BZP) + częściowo unijne
- Filtr po: CPV, województwie, dacie publikacji, procedurze
- Działa tylko dla Polski

### TED Search API v3
- Ogłoszenia unijne ze wszystkich krajów UE/EOG
- Filtr po: CPV, kraju (`buyer-country`), regionie NUTS (`place-of-performance`), dacie
- Nie wymaga klucza API
- Paginacja w trybie ITERATION (bez limitu 15k)
- XML ogłoszeń pobierany na żądanie dla streszczeń szczegółowych

## Baza danych

SQLite z tabelami:
- `filter_profiles` — profile filtrów (CPV, województwa, kraje, keywords)
- `notices` — ogłoszenia (dane, user_status ⭐/❌, keyword_hit, is_below_eu)
- `notice_state` — fingerprint do wykrywania zmian
- `summaries` — streszczenia AI: `summary_json` (strukturalne) + `detailed_text` (szczegółowe)
- `ignored_cpv` — ignorowane kody CPV

Migracje wykonywane automatycznie przy starcie. Status otwarte/zakończone obliczany na żywo (nie zapisywany w bazie).

## Licencja

Projekt wewnętrzny.
