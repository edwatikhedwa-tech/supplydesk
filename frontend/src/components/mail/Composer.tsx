import { useRef, useState, type ChangeEvent } from 'react';
import { Loader2, Send, X } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import { useDialogFocus } from '@/hooks/useDialogFocus';
import { RichTextEditor } from './RichTextEditor';
import { readRichTextEditor } from './richTextUtils';

export interface MailComposerContext {
  requestId: number;
  requestName: string;
  supplierId: number;
  supplierName: string;
  to: string;
  subject: string;
  body?: string;
}

interface ComposerProps {
  context: MailComposerContext;
  onClose: () => void;
  onSent: () => void;
}

export function Composer({ context, onClose, onSent }: ComposerProps) {
  const [subject, setSubject] = useState(context.subject);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const editorRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useDialogFocus(dialogRef, editorRef, onClose, !sending);

  const handleSend = async () => {
    if (!subject.trim()) return;
    setSending(true);
    setError('');
    try {
      const { bodyHtml, bodyText } = readRichTextEditor(editorRef.current);
      await api.sendMail({
        request_id: context.requestId,
        supplier: { id: context.supplierId, email: context.to, name: context.supplierName },
        subject,
        body_text: bodyText,
        body_html: bodyHtml,
      });
      onSent();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось отправить письмо');
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/20 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="composer-title"
        className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl border border-ink-200 overflow-hidden"
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-100">
          <h3 id="composer-title" className="text-base font-semibold text-ink-900">Ответить</h3>
          <button type="button" aria-label="Закрыть форму ответа" onClick={onClose} disabled={sending} className="-mr-1.5 inline-flex min-h-10 min-w-10 items-center justify-center rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-900 disabled:opacity-50">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="mx-5 mt-4 bg-accent-50/50 border border-accent-100 rounded-lg p-3">
          <p className="text-2xs font-semibold text-accent-600 uppercase tracking-wider mb-0.5">Заявка</p>
          <p className="text-sm font-medium text-ink-900">{context.requestName}</p>
          <p className="text-xs text-ink-500 mt-0.5">{context.supplierName}</p>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center gap-3 border-b border-ink-100 pb-2">
            <label className="text-sm text-ink-400 w-12 shrink-0">Кому</label>
            <span className="flex-1 text-sm text-ink-700">{context.to}</span>
          </div>

          <div className="flex items-center gap-3 border-b border-ink-100 pb-2">
            <label className="text-sm text-ink-400 w-12 shrink-0">Тема</label>
            <input
              type="text"
              value={subject}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setSubject(e.target.value)}
              placeholder="Тема письма"
              className="flex-1 text-sm bg-transparent border-none outline-none placeholder:text-ink-300"
            />
          </div>

          <RichTextEditor ref={editorRef} initialHtml={context.body} ariaLabel="Текст письма" placeholder="Напишите письмо..." autoFocus />

          {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        </div>

        <div className="flex items-center justify-end px-5 py-3.5 border-t border-ink-100 bg-ink-50">
          <button
            onClick={handleSend}
            disabled={sending || !subject.trim()}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-accent-600 hover:bg-accent-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            Отправить
          </button>
        </div>
      </div>
    </div>
  );
}
