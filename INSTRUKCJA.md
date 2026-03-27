# TenderBot — Instrukcja obsługi

## Spis treści

1. [Instalacja i pierwsze uruchomienie](#1-instalacja-i-pierwsze-uruchomienie)
2. [Interfejs — przegląd](#2-interfejs--przegląd)
3. [Panel boczny — konfiguracja](#3-panel-boczny--konfiguracja)
4. [Profile filtrów](#4-profile-filtrów)
5. [Monitor — pobieranie ogłoszeń](#5-monitor--pobieranie-ogłoszeń)
6. [Streszczenia AI](#6-streszczenia-ai)
7. [Panel główny — przeglądanie ogłoszeń](#7-panel-główny--przeglądanie-ogłoszeń)
8. [Oznaczanie ogłoszeń](#8-oznaczanie-ogłoszeń)
9. [Ignorowanie kodów CPV](#9-ignorowanie-kodów-cpv)
10. [Typowy workflow](#10-typowy-workflow)
11. [Zaawansowane — linia poleceń](#11-zaawansowane--linia-poleceń)
12. [Rozwiązywanie problemów](#12-rozwiązywanie-problemów)

---

## 1. Instalacja i pierwsze uruchomienie

### Wymagania wstępne

- Python 3.11 lub nowszy
- pip (menedżer pakietów Python)
- Ollama zainstalowana lokalnie (do streszczeń AI)

### Instalacja zależności

```bash
pip install streamlit pandas httpx pydantic ollama
```

Opcjonalnie, jeśli chcesz używać Google Gemini jako backendu AI:

```bash
pip install google-genai
```

### Przygotowanie słownika CPV

Pobierz plik `cpv_2008_ver_2013.csv` i umieść go w tym samym katalogu co `app.py`. Plik powinien zawierać kolumny `CODE` (8-cyfrowy kod CPV) i `PL` (opis po polsku). Bez tego pliku aplikacja uruchomi się, ale wybór kodów CPV w profilu nie będzie działał.

### Uruchomienie

```bash
cd /ścieżka/do/tenderbot/
streamlit run app.py
```

Przy pierwszym uruchomieniu automatycznie:
- Zostanie utworzony katalog `data/`
- Zostanie utworzona baza SQLite `data/tenderbot.sqlite` ze wszystkimi tabelami
- Panel otworzy się w przeglądarce na `http://localhost:8501`

---

## 2. Interfejs — przegląd

Aplikacja składa się z dwóch głównych części:

**Panel boczny (sidebar)** — po lewej stronie:
- Sterowanie jobami (Monitor, Summarize) z live logami
- Konfiguracja modelu AI i liczby streszczeń
- Zarządzanie profilami filtrów
- Lista ignorowanych kodów CPV

**Panel główny** — centralny:
- Pasek filtrów (procedura, profil, status, keywords, oznaczenie, szukaj, ignorowane CPV)
- Statystyki (metryki)
- Lista ogłoszeń z możliwością rozwinięcia szczegółów

---

## 3. Panel boczny — konfiguracja

### Sterowanie jobami

Na górze sidebara znajdują się:

- **Godzin wstecz** — ile godzin wstecz od teraz szukać ogłoszeń. Domyślnie 168 (7 dni). Zmniejsz do np. 24 dla szybszego sprawdzenia, zwiększ do 720 (30 dni) dla szerszego zakresu.

- **Streszczenia na raz** — ile ogłoszeń streszczać w jednym uruchomieniu (domyślnie 10, max 500).

- **▶️ Monitor** — uruchamia `monitor.py`, który pobiera ogłoszenia z Board/Search i TED zgodnie z aktywnym profilem.

- **🧠 Summarize** — uruchamia `summarize.py`, który generuje krótkie streszczenia strukturalne AI dla ogłoszeń, które jeszcze ich nie mają.

Logi z obu jobów wyświetlane są **na żywo** w sidebarze — widzisz postęp linia po linii. Po zakończeniu: ✅ (sukces) lub ❌ (błąd). Pełne logi dostępne w expanderze "📜 Ostatni log".

### Konfiguracja modelu AI

W expanderze **🤖 Model AI (streszczenia)** wybierasz backend:

**Ollama (domyślne)**:
- Model: nazwa modelu dostępnego na serwerze Ollama, np. `kimi-k2.5:cloud`, `qwen3:32b`, `llama3.1:8b`
- Host: adres serwera Ollama, np. `http://localhost:11434`
- API Key: klucz autoryzacji (wymagany dla modeli cloud)

Aby pobrać model cloud:
```bash
ollama pull kimi-k2.5:cloud
ollama pull qwen3:32b
```

**Gemini**:
- Model: np. `gemini-2.5-flash`
- API Key: klucz z Google AI Studio (https://aistudio.google.com/apikey)

Ustawienia z sidebara są przekazywane zarówno do batch streszczeń (🧠 Summarize) jak i streszczeń szczegółowych (📋 Szczegółowe).

---

## 4. Profile filtrów

Profil definiuje jakie ogłoszenia chcesz monitorować. Możesz mieć wiele profili (np. "IT Dolnośląskie", "ITS Cała Polska", "IT Niemcy").

### Tworzenie profilu

1. W sidebarze wybierz **➕ Nowy profil** z listy rozwijanej
2. Wpisz **nazwę profilu** (musi być unikalna)
3. Zaznacz **Aktywny** (tylko aktywne profile są używane przez Monitor)

### Kody CPV

CPV (Common Procurement Vocabulary) to klasyfikacja zamówień. Profil filtruje ogłoszenia po kodach CPV.

- **IT (72* i 48*)** — multiselect z kodami IT. Grupa 72* = usługi informatyczne, 48* = oprogramowanie.
- **✅ Preset IT** — checkbox dodający najczęstsze kody IT jednym kliknięciem.
- **📚 Inne kody CPV** — wyszukiwarka po kodzie lub opisie (np. wpisz "kamera" żeby znaleźć 35125300).
- **✍️ Ręczne prefixy** — wpisz kody ręcznie, oddzielone przecinkami.

Hierarchia CPV: `72000000` to cała grupa 72*. Jeśli dodasz `72000000`, monitor znajdzie też `72253200`, `72110000` itd. Jeśli dodasz konkretny kod jak `35125300`, monitor szuka dokładnie tego kodu.

### Kraje

Wybierz kraje UE/EOG do monitorowania (31 krajów z flagami):
- **Polska (POL)** — ogłoszenia pobierane z Board/Search (krajowe + unijne) oraz TED
- **Inne kraje** (np. DEU, CZE, FRA) — tylko z TED

Możesz wybrać wiele krajów jednocześnie.

### Województwa

Widoczne tylko gdy Polska jest wybrana w krajach. Filtruje polskie ogłoszenia po województwie zamawiającego:
- **Wszystkie** — brak filtra geograficznego
- Odznacz i wybierz konkretne, np. PL02 (dolnośląskie)

Filtr działa zarówno na Board/Search (parametr API + filtr lokalny) jak i TED (kody NUTS2, np. PL02 → PL51).

### Słowa kluczowe (Keywords)

Keywords **nie filtrują** — służą do **tagowania**. Ogłoszenie pasujące do keyword dostaje tag 🏷️ i można je potem filtrować w panelu głównym.

Wpisz jedno słowo kluczowe per linia, np.:
```
fundusze UE
KPO
EFRR
rozpoznawanie tablic
ANPR
```

### Zapis profilu

Kliknij **💾 Zapisz**. Profil zostanie zapisany w bazie. Na dole sidebara widać podsumowanie wszystkich profili z liczbą kodów CPV, województwami i krajami.

### Edycja / usuwanie

Wybierz istniejący profil z listy → zmień ustawienia → **💾 Zapisz**. Lub kliknij **🗑️ Usuń** żeby usunąć profil (ogłoszenia w bazie pozostaną).

---

## 5. Monitor — pobieranie ogłoszeń

Po kliknięciu **▶️ Monitor** system:

1. Ładuje aktywne profile z bazy
2. Pomija ogłoszenia oznaczone jako ❌ (dismissed)
3. **Board/Search** (tylko gdy profil obejmuje Polskę):
   - Wysyła zapytania do API ezamowienia.gov.pl
   - Osobne zapytania dla krajowych (is_below_eu=true) i unijnych (is_below_eu=false)
   - Filtruje lokalnie po CPV i województwie
4. **TED API** (dla wszystkich wybranych krajów):
   - Wysyła zapytanie do TED Search API v3
   - Filtruje po krajach, CPV, regionach NUTS i dacie
5. Deduplikuje wyniki (ten sam object_id nie jest zapisywany dwa razy)
6. Zapisuje nowe/zmienione ogłoszenia do bazy
7. Taguje keyword_hit

Postęp widoczny na żywo w sidebarze:
```
[NEW][PL] abc-123 | Dostawa sprzętu IT | CPV 72000000 | ORG Urząd Miasta
[NEW][TED] ted-105477-2026 | System monitoringu | CPV 35125300 | ORG SPZ ZOZ
[SKIP-CPV] xyz-456 | cpv=39100000
[SKIP-PROV] def-789 | prov=PL10
```

### Logi diagnostyczne

Ustaw `TENDERBOT_DEBUG=1` w zmiennych środowiskowych żeby zobaczyć:
- Każde zapytanie API
- Pominięte ogłoszenia (CPV/województwo)
- Fingerprint zmian

---

## 6. Streszczenia AI

TenderBot oferuje dwa poziomy streszczeń:

### Poziom 1: Streszczenie strukturalne (batch)

Uruchamiane przyciskiem **🧠 Summarize**. Przetwarza wiele ogłoszeń na raz.

Dla ogłoszeń TED automatycznie pobiera XML z serwera TED i parsuje kluczowe tagi eForms (opis przedmiotu, kryteria oceny, warunki udziału, finansowanie UE, czas realizacji, wadium). Dla BZP używa treści HTML z bazy.

Wynik to JSON z polami:
- **Przedmiot** (`scope`) — 2-3 zdania o tym co kupujesz
- **Części zamówienia** (`lots`) — lista z opisami i wartościami
- **Szacunkowa wartość** (`estimated_value`)
- **Czas realizacji** (`execution_period`) — np. "21 dni", "12 miesięcy"
- **Wadium** (`deposit_required`) — kwota/procent lub "nie wymagane"
- **Warunki udziału** (`participation_conditions`) — zdolność finansowa, doświadczenie, kadra (bez boilerplate PZP art. 108/109)
- **Kryteria oceny** (`evaluation_criteria`) — z wagami, np. "Cena 60%"
- **Finansowanie UE** (`eu_funding`) — nazwa programu, np. "Fundusze Europejskie dla Wielkopolski 2021-2027"
- **Ryzyka / flagi** (`risks_and_flags`) — realne ryzyka dla oferenta

Wyświetlane w zakładce **🧠 Streszczenie** po rozwinięciu ogłoszenia. Surowy JSON dostępny w zakładce **📋 JSON**.

### Poziom 2: Streszczenie szczegółowe (per ogłoszenie)

Uruchamiane przyciskiem **📋 Szczegółowe** w wierszu linków ogłoszenia. Działa na żądanie dla jednego ogłoszenia.

Pobiera **pełną treść** (XML z TED lub HTML z BZP) i wysyła do modelu LLM bez wymuszania schematu JSON — model sam decyduje co jest najważniejsze i formatuje wynik jako czytelny tekst z nagłówkami.

Wynik zapisywany w bazie (kolumna `detailed_text`) — przetrwa odświeżenie strony. Wyświetlany w zakładce **📋 Szczegółowe** obok streszczenia strukturalnego.

### Kiedy co używać

| Potrzeba | Narzędzie |
|---|---|
| Szybki przegląd wielu ogłoszeń | 🧠 Summarize (batch) |
| Dogłębna analiza konkretnego ogłoszenia | 📋 Szczegółowe (per ogłoszenie) |
| Pełna treść oryginalna | 🔗 Ogłoszenie (link do źródła) |

---

## 7. Panel główny — przeglądanie ogłoszeń

### Pasek filtrów

Na górze panelu głównego:

| Filtr | Opcje | Opis |
|---|---|---|
| Procedura | Wszystkie / Krajowe (BZP) / Unijne (TED) | Rodzaj procedury zamówieniowej |
| Profil | Wszystkie / nazwa profilu | Filtr po profilu, z którego pochodzi ogłoszenie |
| Status | Wszystkie / Otwarte / Zakończone | Otwarte = deadline w przyszłości (**obliczane na żywo**, nie zapisywane w bazie) |
| Keywords | Wszystkie / Tylko z keyword / Bez keyword | Filtr po tagach 🏷️ |
| Oznaczenie | Aktywne / ⭐ Wybrane / ❌ Odrzucone / Wszystkie | Filtr po oznaczeniu użytkownika |
| Szukaj | tekst | Wyszukiwanie w tytule i nazwie organizacji |

Dodatkowo checkbox **🚫 Ukryj ignorowane CPV** (domyślnie włączony) — ukrywa ogłoszenia zawierające ignorowane kody CPV.

Domyślny filtr statusu to **Otwarte** — ogłoszenie z deadline 2026-03-25 pojawi się tu do 25 marca, potem automatycznie przejdzie do "Zakończone" bez żadnej aktualizacji bazy.

### Metryki

Wiersz z liczbami:
- **Ogłoszenia** — łącznie (po filtrach)
- **🇵🇱 Krajowe** — procedura krajowa (BZP)
- **🇪🇺 Unijne** — procedura unijna (TED)
- **🏷️ Keyword** — z trafieniem keyword
- **⭐ Wybrane** — oznaczone przez użytkownika
- **❌ Odrzucone** — odrzucone przez użytkownika
- **🧠 Streszczenia** — z gotowym streszczeniem AI

### Lista ogłoszeń

Każde ogłoszenie wyświetlane jest jako expander z nagłówkiem:

```
🇪🇺 ⭐🏷️ 🧠 Tytuł ogłoszenia...
103647-2026 · Nazwa Zamawiającego · ⏰ 2026-03-15 (5d)
```

Znaczenie ikon:
- 🇵🇱 / 🇪🇺 — krajowe / unijne
- ⭐ — oznaczone jako wybrane
- 🏷️ — trafienie keyword
- 🧠 — ma streszczenie AI
- ⏰ — deadline w przyszłości (z liczbą dni)
- ❌ — deadline minął

Po rozwinięciu widzisz:

**Rząd linków i akcji:**
```
[🔗 Ogłoszenie] [📂 Postępowanie] [📄 PDF (TED)] [📋 Szczegółowe]
```

- **🔗 Ogłoszenie** — link do pełnej treści (ezamowienia.gov.pl dla BZP, ted.europa.eu dla TED)
- **📂 Postępowanie** — link do platformy e-zamówień (jeśli dostępne)
- **📄 PDF (TED)** — PDF ogłoszenia na TED (jeśli dostępne)
- **📋 Szczegółowe** — generuje szczegółowe streszczenie AI (pełna treść). Po wygenerowaniu pokazuje "✅ gotowe"

**Przyciski akcji:** ⭐ Wybierz / ❌ Odrzuć / ↩ Cofnij

**Kody CPV:** każdy kod osobno z opisem i przyciskiem 🚫 do ignorowania. Już ignorowane kody wyświetlane jako ~~przekreślone~~.

**Meta:** województwo, typ ogłoszenia, profil

**Streszczenia AI** (zakładki, pojawiają się gdy dostępne):
- **🧠 Streszczenie** — strukturalne (warunki, kryteria, ryzyka...)
- **📋 JSON** — surowe dane JSON
- **📋 Szczegółowe** — pełne streszczenie wolnym tekstem (po kliknięciu przycisku)

---

## 8. Oznaczanie ogłoszeń

Każde ogłoszenie ma 3 możliwe statusy:

| Status | Znaczenie | Widoczność |
|---|---|---|
| *(brak)* | Nowe, nieocenione | Filtr "Aktywne" |
| ⭐ Wybrane | Interesujące, do śledzenia | Filtr "Aktywne" i "⭐ Wybrane" |
| ❌ Odrzucone | Nieinteresujące | Filtr "❌ Odrzucone" |

**Domyślnie** filtr jest ustawiony na "Aktywne" — widać nowe + wybrane, odrzucone są ukryte.

**Odrzucone ogłoszenia nie są ponownie pobierane** przez Monitor — ich ID jest pomijane przy kolejnych uruchomieniach.

Przyciskami w ogłoszeniu możesz:
- **⭐ Wybierz** → oznacza jako interesujące
- **❌ Odrzuć** → ukrywa z domyślnego widoku i z kolejnych pobrań
- **↩ Cofnij** → przywraca do stanu "nowe"

---

## 9. Ignorowanie kodów CPV

Pozwala ukryć całe kategorie ogłoszeń, np. jeśli profil IT łapie ogłoszenia dotyczące mebli biurowych (CPV 39100000) przez szerokie zapytanie.

### Ignorowanie kodu

1. Rozwiń dowolne ogłoszenie
2. W sekcji CPV zobaczysz kody z opisami, np. `39130000 — Meble biurowe`
3. Kliknij przycisk **🚫 39130000** przy niechcianym kodzie
4. Kod zostanie dodany do listy ignorowanych
5. Ogłoszenia zawierające ten kod znikną z widoku (jeśli checkbox "Ukryj ignorowane" jest włączony)

### Zarządzanie ignorowanymi

W sidebarze sekcja **🚫 Ignorowane CPV** pokazuje listę:
```
39130000 — Meble biurowe                [↩]
30200000 — Urządzenia komputerowe       [↩]
```

Kliknij **↩** żeby przywrócić kod (usunąć z listy ignorowanych).

### Jak działa filtr

Ogłoszenie jest ukrywane jeśli **jakikolwiek** z jego kodów CPV znajduje się na liście ignorowanych. Dotyczy to zarówno ogłoszeń BZP jak i TED.

---

## 10. Typowy workflow

### Przegląd nowych ogłoszeń (codziennie)

1. Otwórz aplikację
2. Kliknij **▶️ Monitor** → poczekaj na pobranie (logi na żywo)
3. Kliknij **🧠 Summarize** → krótkie streszczenia dla nowych ogłoszeń
4. Przeglądaj listę — domyślnie otwarte, aktywne
5. Niechciane kody CPV → 🚫 ignoruj
6. Niechciane ogłoszenia → ❌ Odrzuć
7. Interesujące → ⭐ Wybierz

### Analiza wybranego ogłoszenia

1. Filtr "⭐ Wybrane" → lista interesujących
2. Rozwiń ogłoszenie → zakładka 🧠 Streszczenie → szybki przegląd warunków
3. Kliknij **📋 Szczegółowe** → pełne streszczenie z XML/HTML
4. Kliknij **🔗 Ogłoszenie** → pełna treść na stronie źródłowej

### Poszerzenie monitoringu

1. Sidebar → Profil filtrów → zmień kraje / województwa / CPV
2. Dodaj nowy profil dla innej branży lub regionu
3. Dodaj keywords do tagowania (np. "cyberbezpieczeństwo", "EFRR")

---

## 11. Zaawansowane — linia poleceń

Skrypty można uruchamiać bezpośrednio, bez Streamlit:

### Monitor

```bash
# Standardowe uruchomienie (7 dni wstecz)
python monitor.py

# Ostatnie 24h, debug
TENDERBOT_HOURS_BACK=24 TENDERBOT_DEBUG=1 python monitor.py

# Bez TED (tylko Board/Search)
TENDERBOT_SKIP_TED=1 python monitor.py

# Szukanie konkretnego ogłoszenia
TENDERBOT_TARGET_ID=08de6a9d python monitor.py
```

### Streszczenia

```bash
# Ollama (domyślne)
OLLAMA_MODEL=qwen3:32b python summarize.py

# Gemini
TENDERBOT_LLM_BACKEND=gemini GOOGLE_API_KEY=xxx python summarize.py

# Więcej na raz
TENDERBOT_SUMMARY_BATCH=50 python summarize.py
```

### Zapytania SQL do bazy

```bash
sqlite3 data/tenderbot.sqlite

-- Ile ogłoszeń per źródło
SELECT
  CASE WHEN object_id LIKE 'ted-%' THEN 'TED' ELSE 'BZP' END as src,
  COUNT(*)
FROM notices GROUP BY src;

-- Ogłoszenia ⭐ z dolnośląskiego
SELECT object_id, order_object, organization_name
FROM notices
WHERE user_status = 'starred' AND organization_province = 'PL02';

-- Ogłoszenia ze streszczeniem szczegółowym
SELECT object_id, substr(detailed_text, 1, 100)
FROM summaries
WHERE detailed_text IS NOT NULL;

-- Ignorowane CPV
SELECT * FROM ignored_cpv;

-- Ogłoszenia z konkretnym CPV
SELECT object_id, order_object
FROM notices
WHERE cpv_code LIKE '%72253200%';

-- Statystyka streszczeń
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN summary_json != '{}' THEN 1 ELSE 0 END) as structured,
  SUM(CASE WHEN detailed_text IS NOT NULL THEN 1 ELSE 0 END) as detailed
FROM summaries;
```

---

## 12. Rozwiązywanie problemów

### "Nie wczytano słownika CPV"

Brak pliku `cpv_2008_ver_2013.csv` obok `app.py`. Pobierz z oficjalnego źródła UE lub przygotuj CSV z kolumnami `CODE` i `PL`.

### Monitor nie znajduje ogłoszeń

1. Sprawdź czy profil jest **Aktywny** (checkbox ✅)
2. Sprawdź zakres "Godzin wstecz" — może być za mały
3. Uruchom z `TENDERBOT_DEBUG=1` i sprawdź logi
4. Sprawdź czy kody CPV pasują (72000000 to grupa, 72253200 to konkretny kod)

### Streszczenia nie działają

1. Sprawdź czy Ollama jest uruchomiona: `curl http://localhost:11434/api/version`
2. Sprawdź czy model jest pobrany: `ollama list`
3. Sprawdź klucz API w panelu bocznym (🤖 Model AI)
4. Zmień backend na Gemini jako alternatywę
5. Sprawdź logi — jeśli model zwraca `<think>` tagi, parser je automatycznie usuwa

### Streszczenie szczegółowe nie działa

1. Sprawdź czy Ollama/Gemini odpowiada (te same kroki co wyżej)
2. Dla TED: sprawdź czy XML jest dostępny pod `https://ted.europa.eu/en/notice/{numer}/xml`
3. Dla BZP: sprawdź czy `html_body` nie jest puste w bazie

### TED zwraca 400 Bad Request

1. Sprawdź logi `[TED ERROR]`
2. Możliwe przyczyny: nieobsługiwane pole w query, nieprawidłowy kod NUTS
3. Wyłącz TED tymczasowo: `TENDERBOT_SKIP_TED=1`

### Ogłoszenia z niewłaściwych województw

Filtr województwa działa na dwóch poziomach:
- Board/Search: parametr API + filtr lokalny (`matches_province`)
- TED: kody NUTS2 w zapytaniu (`place-of-performance=PL51*`)

Ogłoszenie bez informacji o województwie (pole puste) jest przepuszczane — lepiej za dużo niż za mało. Możesz je odrzucić ❌ ręcznie.

### Baza jest za duża

```bash
# Usuń stare ogłoszenia (np. starsze niż 90 dni)
sqlite3 data/tenderbot.sqlite "
  DELETE FROM notices
  WHERE publication_date < date('now', '-90 days');
  DELETE FROM notice_state
  WHERE object_id NOT IN (SELECT object_id FROM notices);
  DELETE FROM summaries
  WHERE object_id NOT IN (SELECT object_id FROM notices);
  VACUUM;
"
```

### Reset bazy

```bash
rm data/tenderbot.sqlite
# Przy następnym uruchomieniu baza zostanie utworzona od nowa
```

### Prze-generowanie streszczeń

```bash
# Usuń wszystkie streszczenia (strukturalne + szczegółowe)
sqlite3 data/tenderbot.sqlite "DELETE FROM summaries;"

# Usuń tylko strukturalne (zachowaj szczegółowe)
sqlite3 data/tenderbot.sqlite "UPDATE summaries SET summary_json = '{}', updated_at = '2000-01-01';"

# Usuń tylko szczegółowe (zachowaj strukturalne)
sqlite3 data/tenderbot.sqlite "UPDATE summaries SET detailed_text = NULL;"
```
