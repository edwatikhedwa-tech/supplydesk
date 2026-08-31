import type { ThreadSummary } from '@/lib/types';

export interface ThreadDisplayStatus {
  label: string;
  title: string;
  className: string;
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
      className: 'bg-sky-50 text-sky-700 ring-sky-200/80',
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
