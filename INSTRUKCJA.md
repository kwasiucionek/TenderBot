# TenderBot — Instrukcja obsługi

## Spis treści

1. [Instalacja i pierwsze uruchomienie](#1-instalacja-i-pierwsze-uruchomienie)
2. [Interfejs — przegląd](#2-interfejs--przegląd)
3. [Panel boczny — konfiguracja](#3-panel-boczny--konfiguracja)
4. [Profile filtrów](#4-profile-filtrów)
5. [Monitor — pobieranie ogłoszeń](#5-monitor--pobieranie-ogłoszeń)
6. [Streszczenia AI](#6-streszczenia-ai)
7. [RAG — wyszukiwanie semantyczne](#7-rag--wyszukiwanie-semantyczne)
8. [Panel główny — przeglądanie ogłoszeń](#8-panel-główny--przeglądanie-ogłoszeń)
9. [Oznaczanie ogłoszeń](#9-oznaczanie-ogłoszeń)
10. [Ignorowanie kodów CPV](#10-ignorowanie-kodów-cpv)
11. [Typowy workflow](#11-typowy-workflow)
12. [Zaawansowane — linia poleceń](#12-zaawansowane--linia-poleceń)
13. [Rozwiązywanie problemów](#13-rozwiązywanie-problemów)

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

**Panel główny** — centralny, dwie zwijane sekcje:
- **🔍 Zapytaj o ogłoszenia (RAG)** — wyszukiwanie semantyczne z odpowiedzią AI
- **Filtry i lista ogłoszeń** — pasek filtrów, statystyki, lista ogłoszeń

Obie sekcje można zwijać i rozwijać klikając nagłówek.

---

## 3. Panel boczny — konfiguracja

### Sterowanie jobami

Na górze sidebara znajdują się:

- **Dni wstecz** — ile dni wstecz od teraz szukać ogłoszeń. Domyślnie 7 dni. Zmniejsz do 1–2 dla szybszego sprawdzenia, zwiększ do 30 dla szerszego zakresu.

- **Streszczenia na raz** — ile ogłoszeń streszczać w jednym uruchomieniu (domyślnie 10, max 500).

- **▶️ Monitor** — uruchamia `monitor.py`, który pobiera ogłoszenia z Board/Search i TED zgodnie z aktywnym profilem.

- **🧠 Summarize** — uruchamia `summarize.py`, który generuje **oba poziomy streszczeń** (strukturalne + szczegółowe) dla nieodrzuconych ogłoszeń, którym brakuje któregokolwiek z nich. Po zakończeniu automatycznie przebudowuje indeks FTS dla RAG.

Logi z obu jobów wyświetlane są **na żywo** w sidebarze. Po zakończeniu: ✅ (sukces) lub ❌ (błąd). Pełne logi dostępne w expanderze "📜 Ostatni log".

### Konfiguracja modelu AI

W expanderze **🤖 Model AI (streszczenia)** wybierasz backend:

**Ollama (domyślne)**:
- Host: adres serwera Ollama, np. `http://localhost:11434`
- API Key: klucz autoryzacji (wymagany dla modeli cloud)
- Model: wybierany z **listy dostępnych modeli** (dropdown ładowany z serwera Ollama). Jeśli Ollama niedostępna — pole tekstowe jako fallback.

Aby pobrać model cloud:
```bash
ollama pull kimi-k2.5:cloud
ollama pull qwen3:32b
```

**Gemini**:
- Model: np. `gemini-2.5-flash`
- API Key: klucz z Google AI Studio (https://aistudio.google.com/apikey)

Ustawienia z sidebara są przekazywane zarówno do batch streszczeń (🧠 Summarize) jak i ręcznego poprawiania streszczenia (✍️ Popraw streszczenie).

---

## 4. Profile filtrów

Profil definiuje jakie ogłoszenia chcesz monitorować. Możesz mieć wiele profili (np. "IT Dolnośląskie", "ITS Cała Polska", "IT Niemcy").

### Tworzenie profilu

1. W sidebarze wybierz **➕ Nowy profil** z listy rozwijanej
2. Wpisz **nazwę profilu** (musi być unikalna)
3. Zaznacz **Aktywny** (tylko aktywne profile są używane przez Monitor)

### Typ zamówienia

Multiselect z opcjami: **Usługi**, **Dostawy**, **Roboty budowlane**. Puste = wszystkie typy. Wpływa zarówno na zapytania do Board/Search (parametr `OrderType`) jak i TED (`contract-nature`).

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

### Zapis profilu

Kliknij **💾 Zapisz**. Profil zostanie zapisany w bazie. Na dole sidebara widać podsumowanie wszystkich profili z liczbą kodów CPV, województwami i krajami.

### Edycja / usuwanie

Wybierz istniejący profil z listy → zmień ustawienia → **💾 Zapisz**. Lub kliknij **🗑️ Usuń** żeby usunąć profil (ogłoszenia w bazie pozostaną).

---

## 5. Monitor — pobieranie ogłoszeń

Po kliknięciu **▶️ Monitor** system:

1. Ładuje aktywne profile z bazy
2. **Board/Search** (tylko gdy profil obejmuje Polskę):
   - Wysyła zapytania do API ezamowienia.gov.pl
   - Osobne zapytania per typ zamówienia (Services/Supplies/Works) i per CPV
   - Filtruje lokalnie po CPV i województwie
3. **TED API** (dla wszystkich wybranych krajów):
   - Wysyła zapytanie do TED Search API v3 z filtrem `contract-nature`
   - Mapuje typ zamówienia z listy per lot (wartość dominująca)
4. Deduplikuje wyniki (ten sam object_id nie jest zapisywany dwa razy)
5. Zapisuje nowe/zmienione ogłoszenia do bazy

Postęp widoczny na żywo w sidebarze:
```
[NEW][PL] abc-123 | Dostawa sprzętu IT | CPV 72000000 | ORG Urząd Miasta
[NEW][TED] ted-105477-2026 | System monitoringu | CPV 35125300 | ORG SPZ ZOZ
[SKIP-CPV] xyz-456 | cpv=39100000
[SKIP-PROV] def-789 | prov=PL10
```

### Logi diagnostyczne

Ustaw `TENDERBOT_DEBUG=1` w zmiennych środowiskowych żeby zobaczyć szczegółowe logi każdego zapytania API.

---

## 6. Streszczenia AI

TenderBot oferuje dwa poziomy streszczeń, generowane **automatycznie w jednym przebiegu** przez **🧠 Summarize**:

### Poziom 1: Streszczenie strukturalne

Generowane batch dla wszystkich ogłoszeń bez streszczenia (lub ze starym). Wynik to JSON z polami:
- **Przedmiot** (`scope`) — 2-3 zdania o tym co kupujesz
- **Części zamówienia** (`lots`) — lista z opisami i wartościami
- **Szacunkowa wartość** (`estimated_value`)
- **Czas realizacji** (`execution_period`) — np. "21 dni", "12 miesięcy"
- **Wadium** (`deposit_required`) — kwota/procent lub "nie wymagane"
- **Warunki udziału** (`participation_conditions`) — zdolność finansowa, doświadczenie, kadra
- **Kryteria oceny** (`evaluation_criteria`) — z wagami, np. "Cena 60%"
- **Finansowanie UE** (`eu_funding`) — nazwa programu
- **Ryzyka / flagi** (`risks_and_flags`) — realne ryzyka dla oferenta

Wyświetlane w zakładce **🧠 Streszczenie** po rozwinięciu ogłoszenia. Surowy JSON w zakładce **📋 JSON**.

### Poziom 2: Streszczenie szczegółowe

Generowane batch dla ogłoszeń bez `detailed_text` (w tym samym przebiegu co strukturalne). Pobiera pełną treść (XML z TED lub HTML z BZP) i wysyła do LLM bez schematu — model sam formatuje wynik z nagłówkami.

Wyświetlane w zakładce **📋 Szczegółowe**.

### Ręczne poprawianie

Przycisk **✍️ Popraw streszczenie** w każdym ogłoszeniu — regeneruje szczegółowe streszczenie na żądanie, nadpisując istniejące. Przydatne gdy chcesz użyć lepszego/innego modelu dla wybranego ogłoszenia.

### Logika Summarize

- Pomija ogłoszenia oznaczone jako ❌ (dismissed)
- Dla każdego ogłoszenia sprawdza osobno: brak strukturalnego? brak szczegółowego?
- Treść (XML/HTML) pobierana raz, używana do obu streszczeń
- Po zakończeniu automatycznie przebudowuje indeks FTS dla RAG

---

## 7. RAG — wyszukiwanie semantyczne

Sekcja **🔍 Zapytaj o ogłoszenia (RAG)** umożliwia przeszukiwanie bazy streszczeń pytaniem w języku naturalnym.

### Jak działa

1. Pytanie jest zamieniane na zapytanie FTS5 (SQLite Full-Text Search)
2. System zwraca najbardziej pasujące streszczenia
3. LLM generuje odpowiedź na podstawie znalezionych fragmentów
4. Pod odpowiedzią wyświetlane są źródłowe ogłoszenia (identycznie jak na liście)

### Użycie

1. Wpisz pytanie w polu tekstowym, np.:
   - *"Jakie ogłoszenia dotyczą rozpoznawania tablic rejestracyjnych?"*
   - *"Znajdź przetargi z finansowaniem z KPO"*
   - *"Które ogłoszenia wymagają doświadczenia z systemami AI?"*
2. Kliknij **🔍 Szukaj**
3. Przeczytaj odpowiedź LLM
4. Przejrzyj źródłowe ogłoszenia poniżej (zwijane)

### Opcje

- **Uwzględnij zakończone** — checkbox; domyślnie RAG zwraca tylko ogłoszenia z aktywnym deadline
- **Sortuj źródła** — selectbox z opcjami: trafność, deadline, data publikacji, oznaczone najpierw, krajowe/unijne najpierw, typ zamówienia
- **🔄 Przebuduj indeks FTS** — ręczna przebudowa indeksu (normalnie dzieje się automatycznie po Summarize)

### Jakość wyników

RAG działa na streszczeniach AI — im więcej ogłoszeń ma wygenerowane streszczenia, tym lepsze wyniki. Uruchom **🧠 Summarize** przed korzystaniem z RAG.

---

## 8. Panel główny — przeglądanie ogłoszeń

### Filtry (pasek nad listą)

| Filtr | Opis |
|---|---|
| **Procedura** | Wszystkie / Krajowe (BZP) / Unijne (TED) |
| **Profil** | Filtruje po profilu z którego pochodzi ogłoszenie |
| **Status** | Wszystkie / Otwarte (deadline w przyszłości) / Zakończone |
| **Oznaczenie** | Aktywne (nowe+wybrane) / ⭐ Wybrane / ❌ Odrzucone |
| **Typ zamówienia** | Wszystkie / Usługi / Dostawy / Roboty budowlane |
| **🔍 Szukaj** | Wyszukiwanie tekstowe po tytule i nazwie org. |
| **🚫 Ukryj ignorowane CPV** | Checkbox; ukrywa ogłoszenia z ignorowanymi kodami |

### Metryki

Powyżej listy widoczne liczniki: ogłoszenia ogółem, krajowe, unijne, wybrane, odrzucone, ze streszczeniami.

### Ogłoszenie (zwinięte)

Nagłówek: `🇵🇱/🇪🇺 ⭐ 🧠 **Tytuł ogłoszenia**`
Pod spodem: numer · organizacja · deadline (Xd)

Kliknij nagłówek żeby rozwinąć szczegóły.

### Ogłoszenie (rozwinięte)

**Linki (4 kolumny):**
- 🔗 Ogłoszenie — strona źródłowa
- 📂 Postępowanie — link do postępowania (BZP)
- 📄 PDF — plik PDF (TED)
- ✍️ Popraw streszczenie — ręczna regeneracja szczegółowego streszczenia

**Przyciski akcji:** ⭐ Wybierz / ❌ Odrzuć / ↩ Cofnij

**Kody CPV:** każdy kod osobno z opisem i przyciskiem 🚫 do ignorowania. Już ignorowane wyświetlane jako ~~przekreślone~~.

**Meta:** województwo, typ ogłoszenia, profil

**Streszczenia AI** (zakładki, pojawiają się gdy dostępne):
- **🧠 Streszczenie** — strukturalne (warunki, kryteria, ryzyka...)
- **📋 JSON** — surowe dane JSON
- **📋 Szczegółowe** — pełne streszczenie wolnym tekstem

---

## 9. Oznaczanie ogłoszeń

Każde ogłoszenie ma 3 możliwe statusy:

| Status | Znaczenie | Widoczność |
|---|---|---|
| *(brak)* | Nowe, nieocenione | Filtr "Aktywne" |
| ⭐ Wybrane | Interesujące, do śledzenia | Filtr "Aktywne" i "⭐ Wybrane" |
| ❌ Odrzucone | Nieinteresujące | Filtr "❌ Odrzucone" |

**Domyślnie** filtr jest ustawiony na "Aktywne" — widać nowe + wybrane, odrzucone są ukryte.

**Odrzucone ogłoszenia nie są ponownie streszczane** przez Summarize i nie są ponownie pobierane przez Monitor.

Przyciskami w ogłoszeniu możesz:
- **⭐ Wybierz** → oznacza jako interesujące
- **❌ Odrzuć** → ukrywa z domyślnego widoku i z kolejnych pobrań/streszczeń
- **↩ Cofnij** → przywraca do stanu "nowe"

---

## 10. Ignorowanie kodów CPV

Pozwala ukryć całe kategorie ogłoszeń, np. jeśli profil IT łapie ogłoszenia dotyczące sprzętu medycznego przez szerokie zapytanie `48*`.

### Ignorowanie kodu

1. Rozwiń dowolne ogłoszenie
2. W sekcji CPV zobaczysz kody z opisami, np. `48814000 — Systemy informacji medycznej`
3. Kliknij przycisk **🚫 48814000** przy niechcianym kodzie
4. Kod zostanie dodany do listy ignorowanych
5. Ogłoszenia zawierające ten kod znikną z widoku (jeśli checkbox "Ukryj ignorowane" jest włączony)

### Zarządzanie ignorowanymi

W sidebarze sekcja **🚫 Ignorowane CPV** pokazuje listę z przyciskami ↩ do przywracania.

### Jak działa filtr

Ogłoszenie jest ukrywane jeśli **jakikolwiek** z jego kodów CPV znajduje się na liście ignorowanych. Dotyczy zarówno ogłoszeń BZP jak i TED.

---

## 11. Typowy workflow

### Przegląd nowych ogłoszeń (codziennie)

1. Otwórz aplikację
2. Kliknij **▶️ Monitor** → poczekaj na pobranie (logi na żywo)
3. Kliknij **🧠 Summarize** → generuje oba poziomy streszczeń + przebudowuje indeks FTS
4. Przeglądaj listę — domyślnie otwarte, aktywne
5. Niechciane kody CPV → 🚫 ignoruj
6. Niechciane ogłoszenia → ❌ Odrzuć
7. Interesujące → ⭐ Wybierz

### Wyszukiwanie semantyczne (RAG)

1. Rozwiń sekcję **🔍 Zapytaj o ogłoszenia (RAG)**
2. Wpisz pytanie np. *"Jakie przetargi dotyczą parkingów i zarządzania ruchem?"*
3. Kliknij **🔍 Szukaj** → przeczytaj odpowiedź
4. Przejrzyj źródłowe ogłoszenia poniżej, posortuj wg deadline lub trafności
5. Interesujące → ⭐ Wybierz

### Analiza wybranego ogłoszenia

1. Filtr "⭐ Wybrane" → lista interesujących
2. Rozwiń ogłoszenie → zakładka 🧠 Streszczenie → szybki przegląd warunków
3. Zakładka 📋 Szczegółowe → pełne streszczenie (wygenerowane automatycznie przez Summarize)
4. Jeśli streszczenie niekompletne → **✍️ Popraw streszczenie** z lepszym modelem
5. Kliknij **🔗 Ogłoszenie** → pełna treść na stronie źródłowej

### Poszerzenie monitoringu

1. Sidebar → Profil filtrów → zmień kraje / województwa / CPV / typ zamówienia
2. Dodaj nowy profil dla innej branży lub regionu

---

## 12. Zaawansowane — linia poleceń

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
# Ollama (domyślne) — oba poziomy streszczeń, pomija dismissed
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

-- Statystyka streszczeń (strukturalne + szczegółowe)
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN summary_json != '{}' THEN 1 ELSE 0 END) as structured,
  SUM(CASE WHEN detailed_text IS NOT NULL AND detailed_text != '' THEN 1 ELSE 0 END) as detailed
FROM summaries;

-- Ogłoszenia z konkretnym CPV
SELECT object_id, order_object
FROM notices
WHERE cpv_code LIKE '%72253200%';

-- Ignorowane CPV
SELECT * FROM ignored_cpv;
```

---

## 13. Rozwiązywanie problemów

### "Nie wczytano słownika CPV"

Brak pliku `cpv_2008_ver_2013.csv` obok `app.py`. Pobierz z oficjalnego źródła UE lub przygotuj CSV z kolumnami `CODE` i `PL`.

### Monitor nie znajduje ogłoszeń

1. Sprawdź czy profil jest **Aktywny** (checkbox ✅)
2. Sprawdź zakres "Dni wstecz" — może być za mały
3. Uruchom z `TENDERBOT_DEBUG=1` i sprawdź logi
4. Sprawdź czy kody CPV i typ zamówienia są prawidłowe

### Filtr "Typ zamówienia" nie działa (0 wyników)

Ogłoszenia pobrane starszą wersją mogą mieć `tender_type = NULL`. Uruchom Monitor ponownie — nowe ogłoszenia będą miały poprawny `tender_type`.

### Streszczenia nie działają

1. Sprawdź czy Ollama jest uruchomiona: `curl http://localhost:11434/api/version`
2. Sprawdź czy model jest pobrany: `ollama list`
3. Sprawdź klucz API w panelu bocznym (🤖 Model AI)
4. Zmień backend na Gemini jako alternatywę

### RAG nie znajduje ogłoszeń

1. Sprawdź czy indeks FTS istnieje — kliknij **🔄 Przebuduj indeks FTS**
2. Sprawdź czy ogłoszenia mają streszczenia — uruchom **🧠 Summarize** najpierw
3. Spróbuj prostszego pytania (jedno lub dwa słowa kluczowe)

### TED zwraca 400 Bad Request

1. Sprawdź logi `[TED ERROR]`
2. Możliwe przyczyny: nieobsługiwane pole w query, nieprawidłowy kod NUTS
3. Wyłącz TED tymczasowo: `TENDERBOT_SKIP_TED=1`

### Ogłoszenia zniknęły po zmianie nazwy profilu

Ogłoszenia w bazie mają przypisaną starą nazwę profilu. Uruchom:
```bash
sqlite3 data/tenderbot.sqlite "UPDATE notices SET profile_name = 'NOWA_NAZWA' WHERE profile_name = 'STARA_NAZWA';"
sqlite3 data/tenderbot.sqlite "UPDATE summaries SET profile_name = 'NOWA_NAZWA' WHERE profile_name = 'STARA_NAZWA';"
```

### Baza jest za duża

```bash
# Usuń stare ogłoszenia (np. starsze niż 90 dni)
sqlite3 data/tenderbot.sqlite "
  DELETE FROM notices WHERE publication_date < date('now', '-90 days');
  DELETE FROM notice_state WHERE object_id NOT IN (SELECT object_id FROM notices);
  DELETE FROM summaries WHERE object_id NOT IN (SELECT object_id FROM notices);
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
