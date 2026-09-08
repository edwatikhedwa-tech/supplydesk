"""User tasks (§12 of the approved interface concept) -- an action to take,
distinct from a note (which fixes information). Same zero-coupling
extraction pattern as thread_notes.py / ai_chat_usage.py.
"""

from __future__ import annotations

from typing import Any

from .time_utils import iso_now


class TasksMixin:
    def list_tasks(self, workspace_id: int, user_id: int, *, include_done: bool = False) -> list[dict[str, Any]]:
        clause = "" if include_done else "AND t.done=0"
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT t.id, t.title, t.due_date, t.done, t.request_id, t.supplier_id, t.inbox_message_id,
                           t.created_at, t.completed_at,
                           r.name AS request_name, gs.name AS supplier_name
                    FROM tasks t
                    LEFT JOIN requests r ON r.id = t.request_id
                    LEFT JOIN global_suppliers gs ON gs.id = t.supplier_id
                    WHERE t.workspace_id=? AND t.user_id=? {clause}
                    ORDER BY (t.due_date IS NULL), t.due_date ASC, t.created_at ASC""",
                (workspace_id, user_id),
            ).fetchall()
        items = [dict(row) for row in rows]
        for item in items:
            item["done"] = bool(item["done"])
        return items

    def create_task(
        self, workspace_id: int, user_id: int, *, title: str, due_date: str | None = None,
        request_id: int | None = None, supplier_id: int | None = None, inbox_message_id: int | None = None,
    ) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Укажите текст задачи.")
        now = iso_now()
        with self.connect() as connection:
            if request_id is not None:
                owner = connection.execute("SELECT id FROM requests WHERE id=? AND workspace_id=?", (request_id, workspace_id)).fetchone()
                if not owner:
                    raise ValueError("Заявка не найдена.")
            if supplier_id is not None:
                owner = connection.execute("SELECT id FROM global_suppliers WHERE id=? AND workspace_id=?", (supplier_id, workspace_id)).fetchone()
                if not owner:
                    raise ValueError("Поставщик не найден.")
            cursor = connection.execute(
                """INSERT INTO tasks(workspace_id, user_id, title, due_date, done, request_id, supplier_id, inbox_message_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (workspace_id, user_id, title, due_date or None, request_id, supplier_id, inbox_message_id, now, now),
            )
            task_id = int(cursor.lastrowid)
            self._audit_connection(connection, workspace_id, user_id, "task.created", "task", str(task_id), {"title": title})
            connection.commit()
        return task_id

    def set_task_done(self, workspace_id: int, user_id: int, task_id: int, done: bool) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM tasks WHERE id=? AND workspace_id=? AND user_id=?", (task_id, workspace_id, user_id)).fetchone()
            if not row:
                raise ValueError("Задача не найдена.")
            connection.execute(
                "UPDATE tasks SET done=?, completed_at=?, updated_at=? WHERE id=?",
                (1 if done else 0, now if done else None, now, task_id),
            )
            connection.commit()
        return {"id": task_id, "done": done}

    def delete_task(self, workspace_id: int, user_id: int, task_id: int) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM tasks WHERE id=? AND workspace_id=? AND user_id=?", (task_id, workspace_id, user_id))
            connection.commit()
