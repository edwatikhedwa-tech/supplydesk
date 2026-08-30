import { useEffect, useState, type FormEvent } from 'react';
import { Loader2, Send, X } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import type { InboxMessage } from '@/lib/types';

interface InboxReplyComposerProps {
  message: InboxMessage;
  onClose: () => void;
  onSent: () => void;
}

/**
 * Ответ на письмо без заявки нельзя прятать внизу тела письма: у рассылок
 * содержимое может быть длиннее нескольких экранов. Это отдельный диалог,
 * но он намеренно не меняет привязку письма к заявке и не помечает его
 * прочитанным.
 */
export function InboxReplyComposer({ message, onClose, onSent }: InboxReplyComposerProps) {
  const [subject, setSubject] = useState(() => (
    message.subject.startsWith('Re:') ? message.subject : `Re: ${message.subject || 'Письмо без темы'}`
  ));
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setSubject(message.subject.startsWith('Re:') ? message.subject : `Re: ${message.subject || 'Письмо без темы'}`);
    setBody('');
    setError('');
  }, [message.id, message.subject]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!body.trim()) {
      setError('Напишите текст ответа перед отправкой.');
      return;
    }

    setSending(true);
    setError('');
    try {
      await api.replyToInbox({
        inbox_message_id: message.id,
        subject: subject.trim() || 'Re: Письмо без темы',
        body: body.trim(),
      });
      onSent();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : '';
      setError(
        message && !/^Ошибка запроса \(\d+\)$/.test(message)
          ? message
          : 'Не удалось отправить ответ. Проверьте соединение и попробуйте ещё раз.',
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-ink-900/25 p-4 backdrop-blur-sm">
      <div
        aria-labelledby="inbox-reply-title"
        aria-modal="true"
        role="dialog"
        className="my-auto w-full max-w-2xl overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-2xl"
      >
        <form onSubmit={handleSubmit}>
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-3.5">
          <h3 id="inbox-reply-title" className="text-base font-semibold text-ink-900">Ответить</h3>
          <button
            type="button"
            aria-label="Закрыть форму ответа"
            onClick={onClose}
            disabled={sending}
            className="-mr-1.5 inline-flex min-h-10 min-w-10 items-center justify-center rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900 disabled:opacity-50"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="mx-5 mt-4 rounded-xl border border-amber-200 bg-amber-50/70 p-3">
          <p className="text-2xs font-semibold uppercase tracking-wider text-amber-800">Письмо без привязки к заявке</p>
          <p className="mt-1 break-all text-sm font-medium text-ink-900">{message.from_email}</p>
          <p className="mt-1 text-xs leading-5 text-amber-700">Ответ останется в этой переписке и не привяжет письмо к заявке автоматически.</p>
        </div>

        <div className="space-y-3 px-5 py-4">
          <div className="flex items-start gap-3 border-b border-ink-100 pb-2">
            <span className="w-12 shrink-0 pt-1 text-sm text-ink-600">Кому</span>
            <span className="min-w-0 flex-1 break-all pt-1 text-sm text-ink-700">{message.from_email}</span>
          </div>

          <div className="flex items-center gap-3 border-b border-ink-100 pb-2">
            <label htmlFor="inbox-reply-subject" className="w-12 shrink-0 text-sm text-ink-600">Тема</label>
            <input
              id="inbox-reply-subject"
              type="text"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="min-w-0 flex-1 bg-transparent text-sm text-ink-800 outline-none placeholder:text-ink-300"
              placeholder="Тема письма"
            />
          </div>

          <div>
            <label htmlFor="inbox-reply-body" className="mb-1.5 block text-sm font-medium text-ink-700">Текст ответа</label>
            <textarea
              id="inbox-reply-body"
              autoFocus
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="Напишите ответ…"
              className="min-h-40 w-full resize-y rounded-xl border border-ink-200 px-3 py-2.5 text-sm leading-6 text-ink-800 outline-none transition-colors placeholder:text-ink-300 focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
          </div>

          {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-ink-100 bg-ink-50 px-5 py-3.5">
          <button
            type="button"
            onClick={onClose}
            disabled={sending}
            className="inline-flex min-h-10 items-center rounded-lg px-3 py-1.5 text-sm font-medium text-ink-600 transition-colors hover:bg-ink-200 disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={sending || !body.trim()}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}
            Отправить
          </button>
        </div>
        </form>
      </div>
    </div>
  );
}
