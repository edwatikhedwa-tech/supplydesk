"""User tasks (§12 of the approved interface concept) -- an action to take,
distinct from a note (which fixes information). Same zero-coupling
extraction pattern as thread_notes.py / ai_chat_usage.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .task_reminder_mock import phone_reminders_mode, trigger_due_phone_reminder_mocks
from .time_utils import iso_now


class TasksMixin:
    def list_tasks(self, workspace_id: int, user_id: int, *, include_done: bool = False) -> list[dict[str, Any]]:
        clause = "" if include_done else "AND t.done=0"
        with self.connect() as connection:
            trigger_due_phone_reminder_mocks(connection, mode=phone_reminders_mode())
            rows = connection.execute(
                f"""SELECT t.id, t.title, t.due_date, t.done, t.request_id, t.supplier_id, t.inbox_message_id,
                           t.created_at, t.completed_at,
                           COALESCE(d.description, '') AS description, d.due_at, d.timezone,
                           COALESCE(d.priority, 'normal') AS priority, d.assignee_user_id,
                           assignee.display_name AS assignee_name,
                           r.name AS request_name, gs.name AS supplier_name
                    FROM tasks t
                    LEFT JOIN task_details d ON d.task_id = t.id
                    LEFT JOIN users assignee ON assignee.id = d.assignee_user_id
                    LEFT JOIN requests r ON r.id = t.request_id
                    LEFT JOIN global_suppliers gs ON gs.id = t.supplier_id
                    WHERE t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?) {clause}
                    ORDER BY (t.due_date IS NULL), t.due_date ASC, t.created_at ASC""",
                (workspace_id, user_id, user_id),
            ).fetchall()
        items = [dict(row) for row in rows]
        task_ids = [item['id'] for item in items]
        reminders_by_task: dict[int, list[dict[str, Any]]] = {task_id: [] for task_id in task_ids}
        if task_ids:
            placeholders = ','.join('?' for _ in task_ids)
            with self.connect() as connection:
                reminder_rows = connection.execute(
                    f"""SELECT id, task_id, channel, scheduled_at, timezone, status, recipient, mock_state, created_at
                        FROM task_reminders WHERE task_id IN ({placeholders})
                        ORDER BY scheduled_at ASC, id ASC""",
                    task_ids,
                ).fetchall()
            for reminder in reminder_rows:
                item = dict(reminder)
                reminders_by_task[int(item['task_id'])].append(item)
        for item in items:
            item["done"] = bool(item["done"])
            item['reminders'] = reminders_by_task[item['id']]
        return items

    def list_workspace_members(self, workspace_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT u.id, u.display_name, wm.role
                   FROM workspace_members wm
                   JOIN users u ON u.id = wm.user_id
                   WHERE wm.workspace_id=? AND u.is_active=1
                   ORDER BY u.display_name COLLATE NOCASE, u.id""",
                (workspace_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_task(
        self, workspace_id: int, user_id: int, *, title: str, due_date: str | None = None,
        request_id: int | None = None, supplier_id: int | None = None, inbox_message_id: int | None = None,
        description: str = '', due_at: str | None = None, timezone: str | None = None,
        priority: str = 'normal', assignee_user_id: int | None = None,
        reminders: list[dict[str, Any]] | None = None,
    ) -> int:
        title = title.strip()
        if not title:
            raise ValueError("Укажите текст задачи.")
        description = description.strip()
        if priority not in {'low', 'normal', 'high'}:
            raise ValueError("Некорректный приоритет задачи.")
        normalized_due_at = self._validate_due_at(due_at, timezone)
        if normalized_due_at and not due_date:
            due_date = normalized_due_at[:10]
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
            effective_assignee = assignee_user_id if assignee_user_id is not None else user_id
            assignee = connection.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (workspace_id, effective_assignee),
            ).fetchone()
            if not assignee:
                raise ValueError("Исполнитель должен состоять в этом рабочем пространстве.")
            cursor = connection.execute(
                """INSERT INTO tasks(workspace_id, user_id, title, due_date, done, request_id, supplier_id, inbox_message_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?)""",
                (workspace_id, user_id, title, due_date or None, request_id, supplier_id, inbox_message_id, now, now),
            )
            task_id = int(cursor.lastrowid)
            connection.execute(
                """INSERT INTO task_details(task_id, description, due_at, timezone, priority, assignee_user_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (task_id, description, normalized_due_at, timezone if normalized_due_at else None, priority, effective_assignee),
            )
            self._replace_task_reminders(connection, task_id, user_id, reminders, now)
            self._audit_connection(connection, workspace_id, user_id, "task.created", "task", str(task_id), {"title": title})
            connection.commit()
        return task_id

    def create_or_refresh_followup_task(
        self, workspace_id: int, user_id: int, *, request_id: int, supplier_id: int | None,
        title: str, due_date: str | None = None,
    ) -> dict[str, Any]:
        """Idempotent counterpart to `create_task` for the "Напомнить"
        follow-up action. At most one ACTIVE (`done=0`) task with this exact
        `title` may exist for one `(request_id, supplier_id)` pair at a
        time -- a second "Напомнить" click on the same conversation refreshes
        the existing task's due date instead of creating a duplicate.

        The exact-title match is the only "is this a follow-up task, not an
        unrelated one the user created by hand" signal available without a
        new column: `title` here is always the fixed follow-up default
        (never freely typed by a user through this action), so a genuinely
        different manually-created task for the same request/supplier (a
        different title) is never matched or touched -- and a completed
        follow-up task (`done=1`) is never matched either, so a new
        follow-up after the old one was finished creates a fresh task, not a
        silent no-op.

        `COALESCE(supplier_id, -1) = COALESCE(?, -1)` is used instead of a
        raw `IS`/`= ` comparison so a NULL `supplier_id` (thread not yet
        linked to the global directory) still matches NULL-to-NULL
        consistently on both SQLite and Postgres, which this repository
        supports interchangeably.
        """
        now = iso_now()
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT id FROM tasks
                   WHERE workspace_id=? AND request_id=? AND COALESCE(supplier_id, -1) = COALESCE(?, -1)
                     AND title=? AND done=0
                   ORDER BY id DESC LIMIT 1""",
                (workspace_id, request_id, supplier_id, title),
            ).fetchone()
            if existing:
                task_id = int(existing["id"])
                connection.execute(
                    "UPDATE tasks SET due_date=COALESCE(?, due_date), updated_at=? WHERE id=?",
                    (due_date or None, now, task_id),
                )
                self._audit_connection(
                    connection, workspace_id, user_id, "task.followup_refreshed", "task", str(task_id), {"title": title},
                )
                connection.commit()
                return {"task_id": task_id, "created": False}
        task_id = self.create_task(
            workspace_id, user_id, title=title, due_date=due_date, request_id=request_id, supplier_id=supplier_id,
        )
        return {"task_id": task_id, "created": True}

    @staticmethod
    def _validate_due_at(due_at: str | None, timezone: str | None) -> str | None:
        if not due_at:
            if timezone:
                raise ValueError("Timezone указывается только вместе со временем задачи.")
            return None
        if not timezone:
            raise ValueError("Укажите timezone для времени задачи.")
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Укажите поддерживаемую IANA timezone.") from exc
        try:
            parsed = datetime.fromisoformat(due_at)
        except ValueError as exc:
            raise ValueError("Время задачи должно быть в формате YYYY-MM-DDTHH:MM.") from exc
        if parsed.tzinfo is not None or len(due_at) != 16 or due_at[10] != 'T':
            raise ValueError("Время задачи должно быть локальным YYYY-MM-DDTHH:MM без смещения.")
        return due_at

    def _replace_task_reminders(
        self, connection: Any, task_id: int, user_id: int, reminders: list[dict[str, Any]] | None, now: str,
    ) -> None:
        if reminders is None:
            return
        if not isinstance(reminders, list) or len(reminders) > 5:
            raise ValueError("Можно указать не более пяти напоминаний.")
        normalized: list[tuple[str, str, str, str | None]] = []
        fallback_email_row = connection.execute("SELECT email FROM users WHERE id=?", (user_id,)).fetchone()
        fallback_email = str(fallback_email_row['email']) if fallback_email_row else None
        for reminder in reminders:
            if not isinstance(reminder, dict):
                raise ValueError("Некорректное напоминание.")
            channel = str(reminder.get('channel') or '')
            if channel not in {'in_app', 'email', 'phone'}:
                raise ValueError("Поддерживаются только In-app, Email и phone mock напоминания.")
            if channel == 'phone' and phone_reminders_mode() != 'mock':
                raise ValueError("Телефонные напоминания пока недоступны.")
            scheduled_at = self._validate_due_at(
                str(reminder.get('scheduled_at') or '') or None,
                str(reminder.get('timezone') or '') or None,
            )
            if not scheduled_at:
                raise ValueError("Укажите дату и время напоминания.")
            recipient = str(reminder.get('recipient') or '').strip() or (fallback_email if channel == 'email' else None)
            if channel == 'email' and (not recipient or '@' not in recipient):
                raise ValueError("Укажите корректный Email получателя напоминания.")
            if channel == 'phone' and (not recipient or len(''.join(char for char in recipient if char.isdigit())) < 7):
                raise ValueError("Укажите номер для телефонного напоминания.")
            normalized.append((channel, scheduled_at, str(reminder['timezone']), recipient))
        connection.execute("DELETE FROM task_reminders WHERE task_id=?", (task_id,))
        connection.executemany(
            """INSERT INTO task_reminders(task_id, channel, scheduled_at, timezone, status, recipient, mock_state, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'scheduled', ?, ?, ?, ?)""",
            [(task_id, channel, scheduled_at, zone, recipient, 'mock' if channel == 'phone' else None, now, now) for channel, scheduled_at, zone, recipient in normalized],
        )

    def set_task_done(self, workspace_id: int, user_id: int, task_id: int, done: bool) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            self._require_task_access(connection, workspace_id, user_id, task_id)
            connection.execute(
                "UPDATE tasks SET done=?, completed_at=?, updated_at=? WHERE id=?",
                (1 if done else 0, now if done else None, now, task_id),
            )
            connection.commit()
        return {"id": task_id, "done": done}

    def update_task(
        self, workspace_id: int, user_id: int, task_id: int, *, title: str, description: str = '',
        due_date: str | None = None, due_at: str | None = None, timezone: str | None = None,
        priority: str = 'normal', assignee_user_id: int | None = None, reminders: list[dict[str, Any]] | None = None,
    ) -> None:
        title = title.strip()
        if not title:
            raise ValueError("Укажите текст задачи.")
        description = description.strip()
        if priority not in {'low', 'normal', 'high'}:
            raise ValueError("Некорректный приоритет задачи.")
        normalized_due_at = self._validate_due_at(due_at, timezone)
        if normalized_due_at and not due_date:
            due_date = normalized_due_at[:10]
        now = iso_now()
        with self.connect() as connection:
            task = self._require_task_access(connection, workspace_id, user_id, task_id)
            if task['user_id'] != user_id and assignee_user_id not in (None, task['assignee_user_id']):
                raise PermissionError("Только автор задачи может менять исполнителя.")
            effective_assignee = assignee_user_id if assignee_user_id is not None else (task['assignee_user_id'] or task['user_id'])
            member = connection.execute(
                "SELECT 1 FROM workspace_members WHERE workspace_id=? AND user_id=?",
                (workspace_id, effective_assignee),
            ).fetchone()
            if not member:
                raise ValueError("Исполнитель должен состоять в этом рабочем пространстве.")
            connection.execute(
                "UPDATE tasks SET title=?, due_date=?, updated_at=? WHERE id=?",
                (title, due_date or None, now, task_id),
            )
            connection.execute(
                """INSERT INTO task_details(task_id, description, due_at, timezone, priority, assignee_user_id)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET description=excluded.description, due_at=excluded.due_at,
                     timezone=excluded.timezone, priority=excluded.priority, assignee_user_id=excluded.assignee_user_id""",
                (task_id, description, normalized_due_at, timezone if normalized_due_at else None, priority, effective_assignee),
            )
            self._replace_task_reminders(connection, task_id, user_id, reminders, now)
            self._audit_connection(connection, workspace_id, user_id, "task.updated", "task", str(task_id), {"title": title})
            connection.commit()

    @staticmethod
    def _require_task_access(connection: Any, workspace_id: int, user_id: int, task_id: int) -> Any:
        row = connection.execute(
            """SELECT t.id, t.user_id, d.assignee_user_id FROM tasks t
               LEFT JOIN task_details d ON d.task_id=t.id
               WHERE t.id=? AND t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?)""",
            (task_id, workspace_id, user_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("Задача не найдена.")
        return row

    def delete_task(self, workspace_id: int, user_id: int, task_id: int) -> None:
        with self.connect() as connection:
            task = self._require_task_access(connection, workspace_id, user_id, task_id)
            if task['user_id'] != user_id:
                raise PermissionError("Удалить задачу может только её автор.")
            connection.execute("DELETE FROM tasks WHERE id=? AND workspace_id=?", (task_id, workspace_id))
            connection.commit()
