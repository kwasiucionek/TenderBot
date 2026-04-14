-- ============================================================
-- TenderBot — nowe kody CPV do ignorowania
-- Wygenerowano na podstawie analizy aktywnych ogłoszeń
-- ============================================================

BEGIN;

-- 🖥️ Sprzęt komputerowy (zakup urządzeń, nie usługi IT)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('30200000', 'Urządzenia komputerowe (sprzęt)', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('30210000', 'Maszyny do przetwarzania danych (sprzęt)', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('30213100', 'Komputery przenośne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('30230000', 'Urządzenia komputerowe różne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('48810000', 'Systemy informacyjne ogólne (HR, kadrowe)', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('48800000', 'Systemy i serwery informacyjne', datetime('now'));

-- ✍️ Podpis elektroniczny / uwierzytelnianie
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79132100', 'Usługi uwierzytelniania podpisu elektronicznego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('72212311', 'Oprogramowanie do zarządzania dokumentami', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('42965110', 'Systemy zarządzania dokumentami', datetime('now'));

-- 📋 Usługi biznesowe / zarządzanie / HR (nie IT)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79000000', 'Usługi biznesowe ogólne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79400000', 'Doradztwo gospodarcze i zarządzanie', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79420000', 'Usługi zarządzania ogólne', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79600000', 'Usługi rekrutacji personelu', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79610000', 'Udostępnianie personelu', datetime('now'));

-- 📣 Marketing, reklama, media
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79340000', 'Usługi reklamowe i marketingowe', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79960000', 'Usługi fotograficzne i pomocnicze', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('79980000', 'Usługi prenumerat', datetime('now'));

-- 💳 Płatności, rozliczenia, finanse
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('72416000', 'Przetwarzanie płatności i rozliczanie', datetime('now'));

-- 🗄️ Bazy danych / zarządzanie danymi (ogólne, niebranżowe)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('72320000', 'Usługi bazy danych (prenumeraty naukowe)', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('72322000', 'Zarządzanie danymi (delegat ochrony danych itp.)', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('72330000', 'Standaryzacja i klasyfikacja treści', datetime('now'));

-- 📡 Telekomunikacja (infrastruktura sieciowa, nie IT)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('64200000', 'Usługi telekomunikacyjne', datetime('now'));

-- 🔧 Naprawa i konserwacja sprzętu (nie oprogramowania)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50110000', 'Naprawy pojazdów mechanicznych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50300000', 'Naprawa i konserwacja sprzętu biurowego', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50324100', 'Konserwacja komputerów PC', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('50324200', 'Zapobiegawcza konserwacja PC', datetime('now'));

-- 🚗 Transport i inne niezwiązane
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('60000000', 'Usługi transportowe', datetime('now'));

-- 📸 Aparaty / biometria / sprzęt nadzoru (nie systemy)
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('38651000', 'Aparaty fotograficzne', datetime('now'));

COMMIT;
