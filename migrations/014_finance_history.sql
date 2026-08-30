-- Динамика выручки и прибыли по годам.
--
-- Зачем: /v2/finances возвращает всю доступную историю одним запросом (у
-- крупных ООО это 15 лет), а сохранялся только последний год — остальное
-- отбрасывалось. Между тем для закупщика важен не столько сам оборот, сколько
-- его направление: «выручка растёт, а прибыль падает» — это сигнал, ради
-- которого финансы вообще смотрят. Данные уже оплачены тем же запросом,
-- дополнительной нагрузки на дневной лимит Checko таблица не создаёт.
--
-- Отдельная таблица рядом с global_supplier_finances (там остаётся последний
-- год для быстрых списков) — по правилу проекта новые поля живут в
-- компаньонах, а не в ALTER TABLE.
CREATE TABLE IF NOT EXISTS global_supplier_finance_history (
    global_supplier_id INTEGER NOT NULL REFERENCES global_suppliers(id) ON DELETE CASCADE,
    report_year        INTEGER NOT NULL,
    revenue            BIGINT,
    profit             BIGINT,
    updated_at         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (global_supplier_id, report_year)
);
