import type { ThreadSummary } from '@/lib/types';

export interface ThreadDisplayStatus {
  label: string;
  title: string;
  className: string;
}

/**
 * The primary correspondence list is for mail that reached the provider or
 * has a supplier reply. Queue-only mail belongs to the dedicated outbox.
 * Keep a thread with a reply visible even if its newest outbound attempt has
 * a later transport status, because the conversation still has useful history.
 */
export function isPrimaryCorrespondence(thread: ThreadSummary): boolean {
  return thread.last_outbound_status === 'sent'
    || thread.replies_count > 0
    || thread.last_message_direction === 'inbound';
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
    || ['sending', 'queued', 'failed', 'delivery_unknown'].includes(thread.last_outbound_status ?? '');
}

/** Convert transport/reply facts into one compact, readable list status. */
export function getThreadDisplayStatus(thread: ThreadSummary): ThreadDisplayStatus {
  if (thread.unread_count > 0) {
    return {
      label: 'Новый ответ',
      title: `${thread.unread_count} непрочитанный ответ поставщика`,
      className: 'bg-emerald-50 text-emerald-700 ring-emerald-200/80',
    };
  }

  if (thread.last_message_direction === 'inbound') {
    return {
      label: 'Ответ получен',
      title: 'Ответ поставщика уже прочитан',
      className: 'bg-accent-100 text-accent-800 ring-accent-300 shadow-sm',
    };
  }

  if (thread.last_outbound_status === 'sending') {
    return {
      label: 'Отправляется',
      title: 'Письмо сейчас передаётся почтовому серверу',
      className: 'bg-amber-50 text-amber-800 ring-amber-200/80',
    };
  }

  if (thread.pending_outbound_count > 0 || thread.last_outbound_status === 'queued') {
    return {
      label: 'В очереди',
      title: 'Письмо ещё не передано поставщику',
      className: 'bg-amber-50 text-amber-800 ring-amber-200/80',
    };
  }

  switch (thread.last_outbound_status) {
    case 'sent':
      return {
        label: 'Ожидает ответа',
        title: 'Почтовый сервер принял письмо; ответа пока нет',
        className: 'bg-ink-100 text-ink-700 ring-ink-200/80',
      };
    case 'failed':
      return {
        label: 'Ошибка отправки',
        title: 'Письмо не удалось отправить',
        className: 'bg-rose-50 text-rose-700 ring-rose-200/80',
      };
    case 'delivery_unknown':
      return {
        label: 'Нужна проверка',
        title: 'Результат передачи письма не подтверждён',
        className: 'bg-orange-50 text-orange-800 ring-orange-200/80',
      };
    default:
      return {
        label: 'Переписка',
        title: 'Письмо в переписке',
        className: 'bg-ink-100 text-ink-600 ring-ink-200/80',
      };
  }
}
