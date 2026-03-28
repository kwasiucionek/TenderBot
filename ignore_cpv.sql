-- ============================================================
-- TenderBot — ignorowane kody CPV
-- Wygenerowano na podstawie analizy bazy danych
-- 
-- UWAGA: Zachowane (NIE ignorowane):
--   35125300 - Systemy nadzoru (ANPR, monitoring)
--   34970000 - Urządzenia nadzoru ruchu (ITS)
--   34996000 - Urządzenia sterowania ruchem drogowym (ITS)
--   48813000 - System informacji pasażerskiej (SmartCity)
--   38221000 - GIS (systemy informacji geograficznej)
--   72310000 - Usługi przetwarzania danych (może być ITS)
--   Wszystkie kody 72xxx, 48xxx, 32xxx główne (ogólne IT)
-- ============================================================

BEGIN;

-- 🏥 Systemy medyczne / szpitalne
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('48814000', 'Systemy informacji medycznej', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('48180000', 'Pakiety oprogramowania medycznego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33100000', 'Urządzenia medyczne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33111000', 'Aparatura rentgenowska', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33161000', 'Urządzenia elektrochirurgiczne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33162000', 'Urządzenia do sal operacyjnych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33168000', 'Urządzenia do endoskopii', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33192000', 'Meble medyczne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33195000', 'System monitorowania pacjentów', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50421000', 'Usługi napraw urządzeń medycznych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('85000000', 'Usługi w zakresie zdrowia i opieki społecznej', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('85120000', 'Usługi opieki zdrowotnej', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90524000', 'Usługi w zakresie odpadów medycznych', datetime('now'));

-- 🎓 Edukacja i szkolenia
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80000000', 'Usługi edukacyjne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80400000', 'Usługi kształcenia dorosłych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80420000', 'Usługi e-learning', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80500000', 'Usługi szkoleniowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80510000', 'Usługi szkolenia specjalistycznego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80511000', 'Usługi szkolenia personelu', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80530000', 'Usługi szkolenia zawodowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80531000', 'Usługi szkolenia zawodowego i technicznego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80533100', 'Usługi szkolenia komputerowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80550000', 'Usługi szkolenia w zakresie bezpieczeństwa', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80532000', 'Usługi szkolenia w zarządzaniu', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80521000', 'Usługi opracowywania programów szkoleniowych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('80533200', 'Usługi nauki jazdy', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79995000', 'Usługi zarządzania archiwami', datetime('now'));

-- 💼 HR, kadry, płace
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('48450000', 'Oprogramowanie HR i do rozliczania czasu pracy', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79632000', 'Szkolenia pracownicze', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79414000', 'Usługi doradcze w zakresie zarządzania zasobami ludzkimi', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79412000', 'Usługi doradcze w zakresie zarządzania finansowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79411000', 'Usługi doradcze w zakresie zarządzania ogólnego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('48100000', 'Przemysłowe specyficzne pakiety oprogramowania', datetime('now'));

-- 🌿 Środowisko, gospodarka wodna, leśnictwo
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90700000', 'Usługi środowiska naturalnego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90713000', 'Usługi doradcze w zakresie zaopatrzenia w wodę', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90713100', 'Usługi konsultacyjne dot. zaopatrzenia w wodę i obróbki ścieków', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('71318000', 'Inżynieria środowiska', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('71311000', 'Usługi doradcze w zakresie budownictwa lądowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('71312000', 'Usługi doradcze w zakresie inżynierii konstrukcyjnej', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('71313000', 'Usługi doradcze w zakresie inżynierii środowiska', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('71315200', 'Usługi doradcze w zakresie usług budowlanych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('71600000', 'Usługi w zakresie badań technicznych', datetime('now'));

-- 🎭 Kultura, sport, rekreacja
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('92000000', 'Usługi rekreacyjne, kulturalne i sportowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('92500000', 'Usługi biblioteczne, archiwalne, muzyczne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('92110000', 'Produkcja filmów', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('92111200', 'Produkcja filmów reklamowych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('37532000', 'Gry wideo', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79930000', 'Specjalne usługi projektowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79956000', 'Usługi organizacji targów i wystaw', datetime('now'));

-- 🏗️ Roboty budowlane i instalacyjne
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45000000', 'Roboty budowlane', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45300000', 'Roboty instalacyjne w budynkach', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45310000', 'Roboty instalacyjne elektryczne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45311000', 'Roboty w zakresie okablowania elektrycznego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45400000', 'Roboty wykończeniowe w zakresie obiektów budowlanych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45430000', 'Pokrywanie podłóg i ścian', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45440000', 'Roboty malarskie i szklarskie', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45450000', 'Roboty budowlane wykończeniowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45215140', 'Roboty budowlane w zakresie obiektów szpitalnych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45330000', 'Roboty instalacyjne wodno-kanalizacyjne', datetime('now'));

-- 🛋️ Meble i wyposażenie
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39000000', 'Meble (włącznie z biurowymi)', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39100000', 'Meble', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39111000', 'Siedziska', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39130000', 'Meble biurowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39150000', 'Różne meble i wyposażenie', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39120000', 'Stoły, kredensy, biurka', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('39154000', 'Sprzęt wystawowy', datetime('now'));

-- 🧪 Sprzęt laboratoryjny i badawczy
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('33696500', 'Odczynniki laboratoryjne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('38430000', 'Aparatura do wykrywania i analizy', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('38434580', 'Analizatory biologiczne', datetime('now'));

-- 💰 Usługi finansowe i ubezpieczeniowe
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('66000000', 'Usługi finansowe i ubezpieczeniowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('66114000', 'Usługi leasingu finansowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('66171000', 'Usługi doradztwa finansowego', datetime('now'));

-- 🏛️ Administracja publiczna (zagraniczne lokalne)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('75000000', 'Usługi administracji publicznej i obrony', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('75131000', 'Usługi rządowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('75241000', 'Usługi bezpieczeństwa publicznego', datetime('now'));

-- 📦 Pozostałe nieistotne
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('44613700', 'Pojemniki na odpady', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('51000000', 'Usługi instalowania', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('51400000', 'Usługi instalowania sprzętu medycznego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('51500000', 'Usługi instalowania maszyn i urządzeń', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('51610000', 'Usługi instalowania sprzętu komputerowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50000000', 'Usługi naprawcze i konserwacyjne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50800000', 'Różne usługi w zakresie napraw i konserwacji', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('42959000', 'Zmywarki do naczyń niedomowego użytku', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('35100000', 'Urządzenia ratunkowe i bezpieczeństwa', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('35112000', 'Sprzęt ratunkowy i bezpieczeństwa', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('31500000', 'Urządzenia oświetleniowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('31520000', 'Lampy i oprawy oświetleniowe', datetime('now'));

COMMIT;
