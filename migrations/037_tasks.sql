PRAGMA foreign_keys = ON;

-- User tasks (§12 of the approved interface concept): a task fixes an
-- ACTION ("Позвонить поставщику завтра"), distinct from a note, which fixes
-- INFORMATION. A brand-new entity -- SupplyDesk had no task concept before
-- this migration, so this is a normal CREATE TABLE, not the
-- additive-only-column workaround the 034/035/036 comments explain (that
-- constraint only bites on ALTER TABLE ADD COLUMN to an existing table).
--
-- due_date is a plain date (YYYY-MM-DD), not a datetime: the Dashboard only
-- needs to bucket tasks into "просрочено / сегодня / скоро", which is a
-- date comparison. A task whose title says "...завтра в 11:00" carries that
-- detail in free text, same as the concept doc's own example -- there is no
-- separate structured due-time field in this first version.
--
-- request_id and supplier_id are both optional and independent (a task can
-- link to a request, a supplier, both, or neither) per the doc's "Задачи
-- могут быть связаны с: заявкой; поставщиком; письмом; другим объектом" --
-- inbox_message_id covers the "письмом" case for a not-yet-linked email.
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    due_date TEXT,
    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    request_id INTEGER,
    supplier_id INTEGER,
    inbox_message_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES global_suppliers(id) ON DELETE CASCADE,
    FOREIGN KEY (inbox_message_id) REFERENCES mail_inbox_messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_workspace_user_done_due
    ON tasks(workspace_id, user_id, done, due_date);
