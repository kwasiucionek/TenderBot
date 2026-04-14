-- TenderBot — ignorowane kody CPV (drogi, zieleń, sprzątanie)
BEGIN;
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90620000', 'Usługi odśnieżania', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45233220', 'Roboty w zakresie nawierzchni dróg', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45232410', 'Roboty w zakresie kanalizacji ściekowej', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45233142', 'Roboty w zakresie naprawy dróg', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45233150', 'Roboty w zakresie regulacji ruchu', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45233221', 'Malowanie nawierzchni', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45233222', 'Roboty w zakresie układania chodników i asfaltowania', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45233280', 'Wznoszenie barier drogowych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('45442121', 'Malowanie budowli', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('77211400', 'Usługi wycinania drzew', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('77310000', 'Usługi sadzenia roślin oraz utrzymania terenów zielonych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90470000', 'Usługi czyszczenia kanałów ściekowych', datetime('now'));
INSERT OR IGNORE INTO ignored_cpv(cpv_code, description, ignored_at) VALUES ('90910000', 'Usługi sprzątania', datetime('now'));
COMMIT;
