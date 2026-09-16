import { Bell, Check, Clock } from 'lucide-react';
import { forwardRef, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useReminders } from '../lib/RemindersContext';
import { formatCompanyName } from '../lib/format';
import { formatReminderDueLabel } from '../lib/taskSchedule';
import type { ReminderAlert } from '../lib/types';

function openTarget(reminder: ReminderAlert): string {
  if (reminder.request_id) return `/requests/${reminder.request_id}`;
  if (reminder.supplier_id) return `/suppliers/${reminder.supplier_id}`;
  return `/?task=${reminder.task_id}`;
}

function FeedRow({ reminder, onAct }: { reminder: ReminderAlert; onAct: () => void }) {
  const { complete, markRead } = useReminders();
  const navigate = useNavigate();
  const unread = !reminder.read_at;

  return (
    <button
      type="button"
      onClick={() => {
        void markRead(reminder.reminder_id);
        navigate(openTarget(reminder));
        onAct();
      }}
      className="flex w-full items-start gap-2 border-b border-border px-3 py-2.5 text-left last:border-b-0 hover:bg-surface-hover"
    >
      <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${unread ? 'bg-accent' : 'bg-transparent'}`} aria-hidden />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12.5px] font-medium text-ink">{reminder.title}</span>
        {reminder.supplier_name && <span className="block truncate text-[11px] text-ink-muted">{formatCompanyName(reminder.supplier_name)}</span>}
        <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[10.5px] text-ink-faint">
          <span className="font-medium text-danger">{formatReminderDueLabel(reminder.scheduled_at)}</span>
          {reminder.request_name && <span>· Заявка «{reminder.request_name}»</span>}
        </span>
      </span>
      {reminder.status === 'triggered' && (
        <span
          role="button"
          tabIndex={0}
          aria-label="Отметить выполненной"
          onClick={(e) => { e.stopPropagation(); void complete(reminder.task_id, reminder.reminder_id); }}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); void complete(reminder.task_id, reminder.reminder_id); } }}
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-success-subtle hover:text-success"
        >
          <Check size={12} />
        </span>
      )}
    </button>
  );
}

export const NotificationCenter = forwardRef<HTMLButtonElement, { open: boolean; onToggle: () => void; onClose: () => void; className?: string }>(
  function NotificationCenter({ open, onToggle, onClose, className }, ref) {
    const { feed, markAllRead } = useReminders();
    const panelRef = useRef<HTMLDivElement>(null);
    const unreadCount = feed.filter((item) => !item.read_at).length;

    useEffect(() => {
      if (!open) return;
      function onClickOutside(e: MouseEvent) {
        if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
      }
      document.addEventListener('mousedown', onClickOutside);
      return () => document.removeEventListener('mousedown', onClickOutside);
    }, [open, onClose]);

    return (
      <div className={`relative ${className ?? ''}`}>
        <button
          ref={ref}
          type="button"
          onClick={onToggle}
          aria-label={unreadCount > 0 ? `Уведомления, непрочитанных: ${unreadCount}` : 'Уведомления'}
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-ink-muted hover:bg-surface-hover hover:text-ink"
        >
          <Bell size={17} />
          {unreadCount > 0 && (
            <span className="absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[9.5px] font-semibold leading-none text-white">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
        {open && (
          <div ref={panelRef} className="absolute right-0 top-11 z-50 w-[340px] rounded-lg border border-border bg-surface shadow-xl">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <p className="text-[12.5px] font-semibold text-ink">Уведомления</p>
              {unreadCount > 0 && (
                <button type="button" onClick={() => void markAllRead()} className="text-[11px] font-medium text-accent hover:text-accent-hover">
                  Прочитать все
                </button>
              )}
            </div>
            <div className="max-h-[360px] overflow-auto">
              {feed.length === 0 ? (
                <p className="flex items-center gap-2 px-3 py-6 text-[12px] text-ink-faint"><Clock size={14} /> Пока нет уведомлений</p>
              ) : (
                feed.map((reminder) => <FeedRow key={reminder.reminder_id} reminder={reminder} onAct={onClose} />)
              )}
            </div>
          </div>
        )}
      </div>
    );
  },
);
