# TenderBot — Zasady filtrowania ogłoszeń

## Profil firmy (Neurosoft)

Firma zajmuje się:
- **Sztuczna inteligencja / ML** — modele, wdrożenia AI, computer vision
- **ANPR** — rozpoznawanie tablic rejestracyjnych, systemy wykrywania przejazdów
- **ITS / SmartCity** — inteligentne systemy transportowe, zarządzanie ruchem, miejskie systemy IT
- **Parking** — systemy obsługi parkingów, automatyzacja
- **NLP** — anonimizacja danych, przetwarzanie języka naturalnego, analiza dokumentów
- **Cyberbezpieczeństwo** — jako obszar dodatkowy

---

## Ogłoszenia ZACHOWYWANE

### Wzorce tytułowe (wystarczy dopasowanie w tytule)

| Kategoria | Wzorce (case-insensitive) |
|-----------|--------------------------|
| ANPR | `ANPR`, `license plate`, `number plate`, `kennzeichen`, `nummernschild`, `immatricul`, `kenteken`, `registreringsskyl` |
| Parking | `parking`, `parkeer`, `parkering`, `parcheggi`, `parkhaus` |
| ITS | `ITS`, `intelligent transport`, `traffic management`, `traffic control`, `verkehrsmanagement`, `verkeersmanagement`, `red light camera`, `traffic violation`, `rotlichtüberwach` |
| SmartCity | `smart city`, `smartcity`, `smart traffic` |
| AI/ML | `artificial intelligence`, `machine learning`, `deep learning`, `computer vision`, `video analytics`, `image recognition`, `object detection` |
| NLP | `NLP`, `natural language processing`, `anonymisation`, `anonymization`, `language model`, `LLM` |
| Cyber | `cybersecurity`, `cybersecur`, `pentest`, `penetration test`, `threat intelligence` |

### Wzorce streszczeniowe (mocniejsze — muszą być tematem głównym)

- **ANPR, parking, ITS, SmartCity, AI, NLP** — jak wyżej, ale szukane w treści streszczenia
- **Cyberbezpieczeństwo** — tylko gdy: słowo `cybersecur` pojawia się **2 razy lub więcej** w streszczeniu, LUB gdy tytuł zawiera `pentest`, `threat intelligence`, `security audit`, `SOC`

---

## Ogłoszenia ODRZUCANE

### Kody CPV do ignorowania (nie pobierane przez monitor)

Kategorie ignorowane przez `ignored_cpv`:
- **Medyczne** — 48814000, 48180000, 33100000, 33111000, 33161000, 33162000, 33168000, 33192000, 33195000, 85000000, 85120000, 90524000
- **Edukacja** — 80000000, 80400000, 80420000, 80500000, 80510000, 80511000, 80530000, 80531000, 80533100, 80550000
- **HR/kadry** — 48450000, 79632000, 79414000, 79411000
- **Środowisko/leśnictwo** — 90700000, 90713000, 71311000–71315200, 71600000
- **Kultura/sport** — 92000000, 92500000, 92110000, 37532000
- **Roboty budowlane** — 45000000, 45300000–45450000
- **Meble** — 39000000–39154000
- **Finanse** — 66000000, 66114000, 66171000
- **Administracja publiczna** — 75000000, 75131000, 75241000

### Wzorce auto-dismiss w monitorze (`_AUTO_DISMISS_TITLE` / `_AUTO_DISMISS_ORG`)

**Tytuł:**
- Medyczne: `szpital`, `klinik`, `ZOZ`, `SPZOZ`, `medyczn`, `zdrowia`, `pacjent`, `EDM`, `HIS`, `RIS`, `PACS`, `AMMS`, `InfoMedica`, `Clininet`, `radiolog`, `endoskop`, `mikrobiologiczn`
- Edukacja: `szkoł`, `uczelni`, `kształcen`, `e-learning`, `Moodle`, `LMS`, `utbildningssystem`
- HR: `kadrowo-płac`, `kadry i płace`, `płacowy`, `kadrowy`, `tijdsregistratie`, `payroll`
- Geodezja: `BDOT`, `GESUT`, `topograficzn`, `ewidencji gruntów`, `punktów granicznych`
- Media/kultura: `TVP`, `telewizj`, `bibliotek`, `muzeum`, `teatr`, `sportow`
- Lokalne usługi: `pomocy społeczn`, `socjaln`, `windykacyjno`, `Strefy Płatnego Parkowania`
- Zagraniczne lokalne: `Gemeinde`, `ville de`, `Stadtwerk`, `kommunal`, `Krankenhaus`, `Spital`, `hôpital`, `sjukhus`, `nemocnic`, `škol`, `Schule`, `universit`

**Organizacja:**
- Szpitale PL: `Szpital`, `Klinika`, `ZOZ`, `Centrum Onkologii`, `Centrum Zdrowia`, `Opieki Zdrowotnej`
- Media: `Telewizja Polska`, `TVP`
- Leśnictwo: `Lasy Państwowe`
- Zagraniczne szpitale: `Krankenhaus`, `Klinikum`, `Spital`, `Hospital`, `Centre Hospitalier`
- Zagraniczne uczelnie: `Universität`, `Université`, `Universidad`, `Università`, `University`
- Zagraniczne komunalne: `Stadt`, `Gemeinde`, `Kommune`, `Ayuntamiento`, `Municipio`, `Ville de`, `Commune de`

---

## Zasada dla ogłoszeń zagranicznych (TED)

**Ogólna reguła:** Ogłoszenia zagraniczne są odrzucane domyślnie, chyba że tytuł lub streszczenie zawierają wzorzec z profilu firmy (ANPR, parking, ITS, SmartCity, AI, NLP, cyber jako temat główny).

Przy masowym czyszczeniu użyty skrypt (`dismiss_foreign.sql`) zachowuje ~25 ogłoszeń z 562 zagranicznych.

### Ogłoszenia zagraniczne wątpliwe (weryfikować ręcznie po czyszczeniu):
- Ogłoszenia z ogólnym tytułem "Usługi informatyczne" — TED często nie ujawnia tematu w tytule
- Greckie ogłoszenia SmartCity — bywają bardzo lokalne mimo nazwy
- Ogłoszenia z kategorii `cyber` przez wzmiankę w streszczeniu — sprawdź czy cybersec jest przedmiotem głównym

---

## Polecenia SQL do masowego czyszczenia

### Usuń ogłoszenia z ignorowanych kodów CPV:
```sql
DELETE FROM summaries WHERE object_id IN (
    SELECT n.object_id FROM notices n
    WHERE EXISTS (SELECT 1 FROM ignored_cpv ic WHERE n.cpv_code LIKE '%' || ic.cpv_code || '%')
);
DELETE FROM notice_state WHERE object_id IN (
    SELECT n.object_id FROM notices n
    WHERE EXISTS (SELECT 1 FROM ignored_cpv ic WHERE n.cpv_code LIKE '%' || ic.cpv_code || '%')
);
DELETE FROM notices WHERE EXISTS (
    SELECT 1 FROM ignored_cpv ic WHERE notices.cpv_code LIKE '%' || ic.cpv_code || '%'
);
```

### Usuń odrzucone:
```sql
DELETE FROM summaries WHERE object_id IN (SELECT object_id FROM notices WHERE user_status = 'dismissed');
DELETE FROM notice_state WHERE object_id IN (SELECT object_id FROM notices WHERE user_status = 'dismissed');
DELETE FROM notices WHERE user_status = 'dismissed';
VACUUM;
```
