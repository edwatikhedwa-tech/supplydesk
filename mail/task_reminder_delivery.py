"""Real delivery-state tracking for `in_app` task reminders.

Before this, an `in_app` reminder was a row created in `task_reminders` and
then never read by anything -- the channel existed in the create/update form
but no toast, notification center or badge ever surfaced it. This module is
the missing other half: it decides when a scheduled reminder becomes due,
persists that transition, and exposes dismiss/snooze/read actions so the
frontend's toast + Notification Center reflect real, durable state instead
of anything computed only in memory.

Snooze/dismiss intentionally never touch `tasks.due_date` / `task_details.due_at`
-- those describe the task itself; a reminder is only the attention mechanism
pointing at it (see docs/product's Task -> Reminder -> Notification diagram).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .time_utils import iso_now


def _reminder_due_at_utc(scheduled_at: str, tz_name: str) -> datetime:
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        zone = dt_timezone.utc
    local = datetime.fromisoformat(scheduled_at).replace(tzinfo=zone)
    return local.astimezone(dt_timezone.utc)


class TaskReminderDeliveryMixin:
    def list_due_reminders(self, workspace_id: int, user_id: int) -> dict[str, Any]:
        """Promotes every due `scheduled` in-app reminder to `triggered`, then
        returns every currently-active (`triggered`, not yet acted on)
        reminder the caller should be showing right now -- as a toast if new,
        or still-open if the page was reloaded, since the toastId dedups.
        """
        now_utc = datetime.now(dt_timezone.utc)
        with self.connect() as connection:
            candidates = connection.execute(
                """SELECT tr.id, tr.scheduled_at, tr.timezone
                   FROM task_reminders tr
                   JOIN tasks t ON t.id = tr.task_id
                   LEFT JOIN task_details d ON d.task_id = t.id
                   WHERE tr.channel='in_app' AND tr.status='scheduled' AND t.done=0
                     AND t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?)""",
                (workspace_id, user_id, user_id),
            ).fetchall()
            due_ids = [
                int(row["id"]) for row in candidates
                if _reminder_due_at_utc(row["scheduled_at"], row["timezone"]) <= now_utc
            ]
            if due_ids:
                now = iso_now()
                placeholders = ",".join("?" for _ in due_ids)
                connection.execute(
                    f"UPDATE task_reminders SET status='triggered', updated_at=? WHERE id IN ({placeholders})",
                    (now, *due_ids),
                )
                connection.commit()

            rows = connection.execute(
                """SELECT tr.id AS reminder_id, tr.task_id, tr.scheduled_at, tr.timezone, tr.status, tr.read_at,
                          t.title, t.due_date, t.done, t.request_id, t.supplier_id,
                          COALESCE(d.priority, 'normal') AS priority,
                          r.name AS request_name, gs.name AS supplier_name
                   FROM task_reminders tr
                   JOIN tasks t ON t.id = tr.task_id
                   LEFT JOIN task_details d ON d.task_id = t.id
                   LEFT JOIN requests r ON r.id = t.request_id
                   LEFT JOIN global_suppliers gs ON gs.id = t.supplier_id
                   WHERE tr.channel='in_app' AND tr.status='triggered' AND t.done=0
                     AND t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?)
                   ORDER BY tr.scheduled_at ASC""",
                (workspace_id, user_id, user_id),
            ).fetchall()
        return {"server_time": now_utc.isoformat(), "items": [dict(row) for row in rows]}

    def _require_reminder_access(self, connection: Any, workspace_id: int, user_id: int, reminder_id: int) -> Any:
        row = connection.execute(
            """SELECT tr.id, tr.status, tr.timezone, tr.task_id FROM task_reminders tr
               JOIN tasks t ON t.id = tr.task_id
               LEFT JOIN task_details d ON d.task_id = t.id
               WHERE tr.id=? AND t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?)""",
            (reminder_id, workspace_id, user_id, user_id),
        ).fetchone()
        if not row:
            raise ValueError("Напоминание не найдено.")
        return row

    def dismiss_reminder(self, workspace_id: int, user_id: int, reminder_id: int) -> dict[str, Any]:
        """Closing the toast (x). Never changes the task's own status."""
        now = iso_now()
        with self.connect() as connection:
            reminder = self._require_reminder_access(connection, workspace_id, user_id, reminder_id)
            if reminder["status"] != "triggered":
                raise ValueError("Напоминание уже неактивно.")
            connection.execute(
                "UPDATE task_reminders SET status='dismissed', updated_at=? WHERE id=?",
                (now, reminder_id),
            )
            connection.commit()
        return {"reminder_id": reminder_id, "status": "dismissed"}

    def snooze_reminder(
        self, workspace_id: int, user_id: int, reminder_id: int, *,
        minutes: int | None = None, until: str | None = None, timezone_name: str | None = None,
    ) -> dict[str, Any]:
        """"Отложить": reschedules this reminder only. `dueAt`/`due_date` of
        the underlying task are never modified.
        """
        now = iso_now()
        with self.connect() as connection:
            reminder = self._require_reminder_access(connection, workspace_id, user_id, reminder_id)
            zone_name = reminder["timezone"]
            if until:
                if not timezone_name:
                    raise ValueError("Укажите timezone для выбранного времени напоминания.")
                try:
                    datetime.fromisoformat(until)
                except ValueError as exc:
                    raise ValueError("Время отложенного напоминания должно быть в формате YYYY-MM-DDTHH:MM.") from exc
                new_scheduled_at = until
                zone_name = timezone_name
            elif minutes is not None:
                if minutes <= 0:
                    raise ValueError("Интервал отложенного напоминания должен быть положительным.")
                try:
                    zone = ZoneInfo(zone_name)
                except ZoneInfoNotFoundError:
                    zone = dt_timezone.utc
                new_local = datetime.now(zone) + timedelta(minutes=minutes)
                new_scheduled_at = new_local.strftime("%Y-%m-%dT%H:%M")
            else:
                raise ValueError("Укажите minutes или until для отложенного напоминания.")
            connection.execute(
                """UPDATE task_reminders SET status='scheduled', scheduled_at=?, timezone=?, read_at=NULL, updated_at=?
                   WHERE id=?""",
                (new_scheduled_at, zone_name, now, reminder_id),
            )
            connection.commit()
        return {"reminder_id": reminder_id, "status": "scheduled", "scheduled_at": new_scheduled_at, "timezone": zone_name}

    def mark_reminder_read(self, workspace_id: int, user_id: int, reminder_id: int) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            self._require_reminder_access(connection, workspace_id, user_id, reminder_id)
            connection.execute(
                "UPDATE task_reminders SET read_at=COALESCE(read_at, ?) WHERE id=?",
                (now, reminder_id),
            )
            connection.commit()
        return {"reminder_id": reminder_id, "read_at": now}

    def mark_all_reminders_read(self, workspace_id: int, user_id: int) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """UPDATE task_reminders SET read_at=?
                   WHERE read_at IS NULL AND status IN ('triggered', 'dismissed')
                     AND task_id IN (
                       SELECT t.id FROM tasks t LEFT JOIN task_details d ON d.task_id = t.id
                       WHERE t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?)
                     )""",
                (now, workspace_id, user_id, user_id),
            )
            connection.commit()
        return {"ok": True}

    def list_notification_feed(self, workspace_id: int, user_id: int, *, limit: int = 30) -> list[dict[str, Any]]:
        """Notification Center feed: triggered + dismissed in-app reminders
        for undone tasks, newest first, for the bell dropdown's history.
        """
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT tr.id AS reminder_id, tr.task_id, tr.scheduled_at, tr.timezone, tr.status, tr.read_at,
                          t.title, t.due_date, t.done, t.request_id, t.supplier_id,
                          COALESCE(d.priority, 'normal') AS priority,
                          r.name AS request_name, gs.name AS supplier_name
                   FROM task_reminders tr
                   JOIN tasks t ON t.id = tr.task_id
                   LEFT JOIN task_details d ON d.task_id = t.id
                   LEFT JOIN requests r ON r.id = t.request_id
                   LEFT JOIN global_suppliers gs ON gs.id = t.supplier_id
                   WHERE tr.channel='in_app' AND tr.status IN ('triggered', 'dismissed')
                     AND t.workspace_id=? AND (t.user_id=? OR d.assignee_user_id=?)
                   ORDER BY tr.scheduled_at DESC LIMIT ?""",
                (workspace_id, user_id, user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_notification_settings(self, user_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT sound_enabled, browser_notifications_enabled, default_reminder_offset_minutes FROM user_notification_settings WHERE user_id=?",
                (user_id,),
            ).fetchone()
        if not row:
            return {"sound_enabled": True, "browser_notifications_enabled": False, "default_reminder_offset_minutes": 0}
        return {
            "sound_enabled": bool(row["sound_enabled"]),
            "browser_notifications_enabled": bool(row["browser_notifications_enabled"]),
            "default_reminder_offset_minutes": int(row["default_reminder_offset_minutes"]),
        }

    def set_notification_settings(
        self, user_id: int, *, sound_enabled: bool, browser_notifications_enabled: bool,
        default_reminder_offset_minutes: int = 0,
    ) -> dict[str, Any]:
        now = iso_now()
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO user_notification_settings(user_id, sound_enabled, browser_notifications_enabled, default_reminder_offset_minutes, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET sound_enabled=excluded.sound_enabled,
                     browser_notifications_enabled=excluded.browser_notifications_enabled,
                     default_reminder_offset_minutes=excluded.default_reminder_offset_minutes, updated_at=excluded.updated_at""",
                (user_id, 1 if sound_enabled else 0, 1 if browser_notifications_enabled else 0, default_reminder_offset_minutes, now),
            )
            connection.commit()
        return self.get_notification_settings(user_id)
