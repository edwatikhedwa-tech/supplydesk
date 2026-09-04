import type { ThreadSummary } from '@/lib/types';
import type { StatusBadgeTone } from '@/components/ui/StatusBadge';

export interface ThreadDisplayStatus {
  label: string;
  title: string;
  className: string;
  tone: StatusBadgeTone;
}

/**
 * The primary correspondence list is for mail that reached the provider or
 * has a supplier reply. Queue-only and unresolved transport states belong to
 * the dedicated outbox/direct-action flows so the inbox stays focused on
 * conversations that are ready to read.
 */
export function isPrimaryCorrespondence(thread: ThreadSummary): boolean {
  return thread.last_message_direction === 'inbound'
    || thread.last_outbound_status === 'sent'
    || (thread.last_outbound_status == null && thread.messages_count > 0);
}

/** A sent thread with no inbound message yet is the actionable waiting state. */
export function isAwaitingResponse(thread: ThreadSummary): boolean {
  return thread.unread_count === 0
    && thread.last_message_direction !== 'inbound'
    && thread.last_outbound_status === 'sent';
}

/** Keep groups with unread or operationally important threads expanded. */
export function needsThreadAttention(thread: ThreadSummary): boolean {
  return thread.unread_count > 0
    || ['sending', 'queued', 'failed', 'delivery_unknown', 'bounced'].includes(thread.last_outbound_status ?? '');
}

/** Convert transport/reply facts into one compact, readable list status. */
export function getThreadDisplayStatus(thread: ThreadSummary): ThreadDisplayStatus {
  if (thread.unread_count > 0) {
    return {
      label: 'Новый ответ',
      title: `${thread.unread_count} непрочитанный ответ поставщика`,
      className: 'bg-emerald-50 text-emerald-700 ring-emerald-200/80',
      tone: 'success',
    };
  }

  if (thread.last_message_direction === 'inbound') {
    return {
      label: 'Ответ получен',
      title: 'Ответ поставщика уже прочитан',
      className: 'bg-accent-100 text-accent-800 ring-accent-300 shadow-sm',
      tone: 'info',
    };
  }

  if (thread.last_outbound_status === 'sending') {
    return {
      label: 'Отправляется',
      title: 'Письмо сейчас передаётся почтовому серверу',
      className: 'bg-amber-50 text-amber-800 ring-amber-200/80',
      tone: 'warning',
    };
  }

  if (thread.pending_outbound_count > 0 || thread.last_outbound_status === 'queued') {
    return {
      label: 'В очереди',
      title: 'Письмо ещё не передано поставщику',
      className: 'bg-amber-50 text-amber-800 ring-amber-200/80',
      tone: 'warning',
    };
  }

  switch (thread.last_outbound_status) {
    case 'sent':
      return {
        label: 'Ожидает ответа',
        title: 'Почтовый сервер принял письмо; ответа пока нет',
        className: 'bg-ink-100 text-ink-700 ring-ink-200/80',
        tone: 'neutral',
      };
    case 'failed':
      return {
        label: 'Ошибка отправки',
        title: 'Письмо не удалось отправить',
        className: 'bg-rose-50 text-rose-700 ring-rose-200/80',
        tone: 'danger',
      };
    case 'delivery_unknown':
      return {
        label: 'Нужна проверка',
        title: 'Результат передачи письма не подтверждён',
        className: 'bg-orange-50 text-orange-800 ring-orange-200/80',
        tone: 'warning',
      };
    case 'bounced':
      return {
        label: 'Возврат письма',
        title: 'Почтовый сервер вернул отправленное письмо',
        className: 'bg-rose-50 text-rose-700 ring-rose-200/80',
        tone: 'danger',
      };
    default:
      return {
        label: 'Переписка',
        title: 'Письмо в переписке',
        className: 'bg-ink-100 text-ink-600 ring-ink-200/80',
        tone: 'neutral',
      };
  }
}
