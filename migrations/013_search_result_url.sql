-- Прямая ссылка на страницу, по которой поставщик нашёлся в выдаче.
--
-- Зачем: в карточке уже показывалось «Почему найден» — сниппет выдачи, — но
-- проверить его было негде: снабженец видел текст про товар и не мог открыть
-- саму страницу. URL у нас был (SerpRow.url), он просто нигде не сохранялся.
--
-- Отдельная таблица, а не колонка в request_suppliers: по правилу проекта
-- ensure_schema() перезапускает каждый .sql при каждом старте, поэтому
-- ALTER TABLE ADD COLUMN здесь непригоден — новые поля живут в компаньонах.
CREATE TABLE IF NOT EXISTS search_result_sources (
    request_id   INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    supplier_id  INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    position_key TEXT    NOT NULL DEFAULT '',
    url          TEXT    NOT NULL DEFAULT '',
    title        TEXT    NOT NULL DEFAULT '',
    updated_at   TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (request_id, supplier_id, position_key)
);

CREATE INDEX IF NOT EXISTS idx_search_result_sources_request
    ON search_result_sources(request_id, supplier_id);
