import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import { useReminders } from '../lib/RemindersContext';
import { playReminderChime } from '../lib/reminderSound';
import type { ReminderAlert } from '../lib/types';
import { ReminderOverflowToast, ReminderToastCloseButton, TaskReminderToast } from './TaskReminderToast';

const MAX_INDIVIDUAL_TOASTS = 3;
const OVERFLOW_TOAST_ID = 'task-reminder-overflow';

function reminderToastId(reminderId: number): string {
  return `task-reminder-${reminderId}`;
}

function openTarget(reminder: ReminderAlert): string {
  if (reminder.request_id) return `/requests/${reminder.request_id}`;
  if (reminder.supplier_id) return `/suppliers/${reminder.supplier_id}`;
  return `/?task=${reminder.task_id}`;
}

/** Mounted once (in AppShell) alongside <ToastContainer/>. Owns no reminder
 * state of its own -- it only watches RemindersContext and turns "active"
 * reminders into persistent toasts, playing the chime and firing a browser
 * notification exactly once per newly-triggered reminder, never on every
 * re-render (§2/§7 of the reminder spec). */
export function ReminderToastManager({ onOpenCenter }: { onOpenCenter: () => void }) {
  const { active, settings, complete, dismiss, snooze } = useReminders();
  const navigate = useNavigate();
  const announced = useRef<Set<number>>(new Set());
  const [busyId, setBusyId] = useState<number | null>(null);
  const [errorById, setErrorById] = useState<Record<number, string>>({});

  useEffect(() => {
    const activeIds = new Set(active.map((r) => r.reminder_id));

    // Newly triggered reminders since the last poll: chime + browser notification once.
    for (const reminder of active) {
      if (!announced.current.has(reminder.reminder_id)) {
        announced.current.add(reminder.reminder_id);
        if (settings.sound_enabled) playReminderChime();
        if (settings.browser_notifications_enabled && typeof Notification !== 'undefined' && Notification.permission === 'granted') {
          try {
            new Notification('SupplyDesk', {
              body: [reminder.title, reminder.supplier_name, reminder.request_name ? `Заявка #${reminder.request_id ?? ''}` : ''].filter(Boolean).join('\n'),
              tag: reminderToastId(reminder.reminder_id),
            });
          } catch {
            // Never let a browser-notification failure affect the in-app toast.
          }
        }
      }
    }
    // Reminders no longer active (completed/dismissed/snoozed elsewhere,
    // e.g. from the Notification Center) must have their toast closed too.
    for (const id of announced.current) {
      if (!activeIds.has(id)) {
        toast.dismiss(reminderToastId(id));
        announced.current.delete(id);
      }
    }

    const visible = [...active].sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
    const shown = visible.slice(0, MAX_INDIVIDUAL_TOASTS);
    const overflowCount = visible.length - shown.length;

    for (const reminder of shown) {
      const id = reminderToastId(reminder.reminder_id);
      toast(
        <TaskReminderToast
          reminder={reminder}
          busy={busyId === reminder.reminder_id}
          error={errorById[reminder.reminder_id] ?? null}
          onComplete={async () => {
            setBusyId(reminder.reminder_id);
            setErrorById((prev) => ({ ...prev, [reminder.reminder_id]: '' }));
            try {
              await complete(reminder.task_id, reminder.reminder_id);
              toast.dismiss(id);
            } catch {
              setErrorById((prev) => ({ ...prev, [reminder.reminder_id]: 'Не удалось сохранить. Попробуйте ещё раз.' }));
            } finally {
              setBusyId(null);
            }
          }}
          onSnooze={async (input) => {
            setBusyId(reminder.reminder_id);
            setErrorById((prev) => ({ ...prev, [reminder.reminder_id]: '' }));
            try {
              await snooze(reminder.reminder_id, input);
              toast.dismiss(id);
            } catch {
              setErrorById((prev) => ({ ...prev, [reminder.reminder_id]: 'Не удалось отложить. Попробуйте ещё раз.' }));
            } finally {
              setBusyId(null);
            }
          }}
          onOpen={() => navigate(openTarget(reminder))}
        />,
        {
          toastId: id,
          autoClose: false,
          closeOnClick: false,
          draggable: false,
          closeButton: <ReminderToastCloseButton onClick={async () => {
            try {
              await dismiss(reminder.reminder_id);
            } finally {
              toast.dismiss(id);
            }
          }} />,
        },
      );
    }

    if (overflowCount > 0) {
      toast(<ReminderOverflowToast count={overflowCount} onOpenCenter={onOpenCenter} />, {
        toastId: OVERFLOW_TOAST_ID, autoClose: false, closeOnClick: false, draggable: false, closeButton: true,
      });
    } else {
      toast.dismiss(OVERFLOW_TOAST_ID);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, settings.sound_enabled, settings.browser_notifications_enabled, busyId, errorById]);

  return null;
}
