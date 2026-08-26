import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, Check, Eye, EyeOff, Send, Loader2, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { Supplier } from '@/lib/types';

interface Props {
  open: boolean;
  suppliers: Supplier[];
  selectedIds: Set<number>;
  onClose: () => void;
  onSend: (ids: number[], subject: string, body: string) => Promise<void>;
}

export function Composer({ open, suppliers, selectedIds, onClose, onSend }: Props) {
  const [subject, setSubject] = useState('Запрос коммерческого предложения');
  const [body, setBody] = useState('Добрый день!\n\nПросим предоставить коммерческое предложение.');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [senderEmail, setSenderEmail] = useState<string | null>(null);
  const [excludedIds, setExcludedIds] = useState<Set<number>>(new Set());
  const [showPreview, setShowPreview] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const allRecipients = useMemo(
    () => suppliers.filter((s) => selectedIds.has(s.id) && s.email),
    [suppliers, selectedIds],
  );
  const recipients = allRecipients.filter((s) => !excludedIds.has(s.id));

  useEffect(() => {
    if (!open) return;
    setExcludedIds(new Set());
    setConfirming(false);
    setShowPreview(false);
    setError('');
    api.mailStatus().then((status) => setSenderEmail(status.connected ? status.email ?? null : null)).catch(() => setSenderEmail(null));
  }, [open]);

  if (!open) return null;

  const toggleExcluded = (id: number) => {
    setExcludedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleSendClick = () => {
    if (recipients.length > 1 && !confirming) {
      setConfirming(true);
      return;
    }
    void doSend();
  };

  const doSend = async () => {
    setSending(true);
    setError('');
    try {
      await onSend(recipients.map((s) => s.id), subject, body);
      onClose();
    } catch {
      setError('Не удалось отправить письма');
    } finally {
      setSending(false);
      setConfirming(false);
    }
  };

  const previewRecipient = recipients[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/20 p-4">
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-white shadow-panel">
        <div className="flex items-center justify-between border-b border-ink-100 px-6 py-4">
          <h2 className="font-semibold text-ink-900">Отправка запроса</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-700"><X className="h-4 w-4" /></button>
        </div>

        <div className="overflow-y-auto px-6 py-4 space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className="text-ink-500">
              Отправитель: <span className="font-medium text-ink-800">{senderEmail ?? 'почта не подключена'}</span>
            </span>
          </div>

          <div className="rounded-lg border border-ink-200">
            <div className="border-b border-ink-100 bg-ink-50/60 px-3 py-2 text-xs font-medium text-ink-600">
              Получатели ({recipients.length}{excludedIds.size > 0 ? ` из ${allRecipients.length}` : ''})
            </div>
            <div className="max-h-40 overflow-y-auto divide-y divide-ink-50">
              {allRecipients.map((s) => {
                const excluded = excludedIds.has(s.id);
                return (
                  <label key={s.id} className={`flex items-center gap-2.5 px-3 py-2 text-xs cursor-pointer ${excluded ? 'opacity-40' : ''}`}>
                    <input type="checkbox" checked={!excluded} onChange={() => toggleExcluded(s.id)} className="accent-accent-600" />
                    <span className="min-w-0 flex-1 truncate font-medium text-ink-800">{s.name}</span>
                    <span className="shrink-0 text-ink-500">{s.email}</span>
                  </label>
                );
              })}
              {allRecipients.length === 0 && (
                <div className="px-3 py-4 text-center text-xs text-ink-400">Нет получателей с email среди выбранных</div>
              )}
            </div>
          </div>

          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Тема письма" className="w-full rounded border border-ink-200 p-2 text-sm" />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} className="w-full rounded border border-ink-200 p-2 text-sm" />

          <button
            onClick={() => setShowPreview((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-accent-600 hover:text-accent-700"
          >
            {showPreview ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            {showPreview ? 'Скрыть предпросмотр' : 'Предпросмотр письма'}
          </button>
          {showPreview && (
            <div className="rounded-lg border border-ink-200 bg-ink-50/40 p-3 text-xs">
              {previewRecipient ? (
                <>
                  <p className="text-ink-500">Кому: <span className="text-ink-800">{previewRecipient.name} &lt;{previewRecipient.email}&gt;</span></p>
                  <p className="mt-1 text-ink-500">Тема: <span className="text-ink-800">{subject || '—'}</span></p>
                  <p className="mt-2 whitespace-pre-wrap text-ink-700">{body}</p>
                  {recipients.length > 1 && <p className="mt-2 text-ink-400">Так же будет отправлено ещё {recipients.length - 1} получателям с той же темой и текстом.</p>}
                </>
              ) : (
                <p className="text-ink-400">Нет получателей для предпросмотра.</p>
              )}
            </div>
          )}

          {error && <p className="text-xs text-rose-600">{error}</p>}

          {confirming && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>Отправить {recipients.length} писем? Отменить будет нельзя.</span>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-ink-100 px-6 py-4">
          <button onClick={onClose} className="rounded px-3 py-2 text-xs text-ink-600">Отмена</button>
          {confirming && (
            <button onClick={() => setConfirming(false)} className="rounded px-3 py-2 text-xs text-ink-600">Назад</button>
          )}
          <button
            disabled={!recipients.length || sending}
            onClick={handleSendClick}
            className={`inline-flex items-center gap-1.5 rounded px-3 py-2 text-xs font-semibold text-white disabled:opacity-50 ${confirming ? 'bg-amber-600 hover:bg-amber-700' : 'bg-accent-600 hover:bg-accent-700'}`}
          >
            {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : confirming ? <Check className="h-3.5 w-3.5" /> : <Send className="h-3.5 w-3.5" />}
            {confirming ? 'Да, отправить' : `Отправить${recipients.length > 1 ? ` (${recipients.length})` : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}
