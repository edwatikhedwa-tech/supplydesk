-- Факторы риска из ЕГРЮЛ/ЕГРИП (Checko /v2/company, /v2/entrepreneur).
--
-- checko_client.Company.risks уже вычислял этот список (ДисквЛица,
-- МассРуковод, МассУчред, НелегалФин, Санкции, СанкцУчр, НедобПост, ЕФРСБ,
-- МассАдрес, недостоверный адрес, недоимка по налогам — поля названы точно
-- как в официальной спецификации checko.ru/integration/api/company), но
-- нигде не сохранялся и не показывался. Отдельная таблица, а не колонка в
-- global_supplier_registry — по правилу проекта новые поля не добавляются
-- через ALTER TABLE.
CREATE TABLE IF NOT EXISTS global_supplier_risks (
    global_supplier_id INTEGER PRIMARY KEY REFERENCES global_suppliers(id) ON DELETE CASCADE,
    risks_json          TEXT NOT NULL DEFAULT '[]',
    updated_at          TEXT NOT NULL DEFAULT ''
);
