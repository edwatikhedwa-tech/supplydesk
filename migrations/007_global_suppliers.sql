PRAGMA foreign_keys = ON;

-- Экран «Поставщики» — картотека поставщика как единого объекта во всех
-- заявках, где он встретился, с дедупликацией по ИНН (не по домену/host,
-- как у suppliers — тот идентификатор остаётся верным для краулинга/
-- обогащения, это отдельный, более крупный идентификатор поверх него).
-- См. docs/suppliers-screen.md.
--
-- ensure_schema() исполняет каждый файл миграции при каждом старте процесса
-- (все существующие — через CREATE TABLE/INDEX IF NOT EXISTS, идемпотентно).
-- Поэтому связь suppliers -> global_suppliers сделана отдельной таблицей, а
-- не через ALTER TABLE ADD COLUMN — тот не идемпотентен и упал бы на втором
-- запуске. По той же причине оценка сделки — отдельная таблица, а не столбец
-- в request_suppliers.

CREATE TABLE IF NOT EXISTS global_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    inn TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    site TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (workspace_id, inn),
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

-- Один host-based supplier (существующая identity для краулинга) принадлежит
-- максимум одной глобальной карточке.
CREATE TABLE IF NOT EXISTS global_supplier_links (
    supplier_id INTEGER PRIMARY KEY,
    global_supplier_id INTEGER NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (global_supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS global_supplier_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    global_supplier_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    correct_inn TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    reported_at TEXT NOT NULL,
    FOREIGN KEY (global_supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE
);

-- Оценка сделки 1-5 — про конкретную (заявка, поставщик) пару, отдельно от
-- responseRate (который считается из mail_messages/request_supplier_states).
CREATE TABLE IF NOT EXISTS request_supplier_ratings (
    request_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (request_id, supplier_id),
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_global_suppliers_workspace ON global_suppliers(workspace_id);
CREATE INDEX IF NOT EXISTS idx_global_supplier_links_global ON global_supplier_links(global_supplier_id);
CREATE INDEX IF NOT EXISTS idx_global_supplier_issues_supplier ON global_supplier_issues(global_supplier_id, reported_at);
