import { Send, Sparkles, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

interface ChatEntry {
  role: 'user' | 'assistant' | 'system-error';
  text: string;
}

export function AiChatPanel({ context, onClose }: { context: string; onClose: () => void }) {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [usage, setUsage] = useState<{ spent_rub: number; limit_rub: number } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .getAiChatUsage()
      .then((res) => setUsage({ spent_rub: res.spent_rub, limit_rub: res.limit_rub }))
      .catch(() => {});
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [entries]);

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setEntries((prev) => [...prev, { role: 'user', text }]);
    setDraft('');
    setSending(true);
    try {
      const res = await api.sendAiChatMessage(text, context);
      setUsage({ spent_rub: res.spent_rub, limit_rub: res.limit_rub });
      if (res.status === 'success' && res.reply) {
        setEntries((prev) => [...prev, { role: 'assistant', text: res.reply as string }]);
      } else {
        setEntries((prev) => [...prev, { role: 'system-error', text: res.message || 'Не удалось получить ответ.' }]);
      }
    } catch {
      setEntries((prev) => [...prev, { role: 'system-error', text: 'Не удалось связаться с ИИ-помощником.' }]);
    } finally {
      setSending(false);
    }
  }

  const capReached = usage !== null && usage.spent_rub >= usage.limit_rub;

  return (
    <div className="flex w-80 shrink-0 flex-col border-l border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-3.5 py-2.5">
        <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
          <Sparkles size={14} />
          ИИ-помощник
        </span>
        <button type="button" onClick={onClose} aria-label="Закрыть ИИ-помощника" className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink">
          <X size={14} />
        </button>
      </div>

      {context && (
        <div className="border-b border-border bg-surface-hover px-3.5 py-2 text-[11px] text-ink-muted">
          Контекст: <span className="text-ink-soft">{context}</span>
        </div>
      )}

      <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto p-3">
        {entries.length === 0 && (
          <p className="text-[12px] text-ink-faint">Спросите что-нибудь про эту заявку или поставщика.</p>
        )}
        {entries.map((entry, i) => (
          <div
            key={i}
            className={
              entry.role === 'user'
                ? 'ml-auto max-w-[85%] rounded-md bg-accent-subtle px-3 py-2 text-[12.5px] text-ink'
                : entry.role === 'assistant'
                  ? 'mr-auto max-w-[85%] rounded-md border border-border bg-canvas px-3 py-2 text-[12.5px] text-ink'
                  : 'mr-auto max-w-[85%] rounded-md border border-danger-border bg-danger-subtle px-3 py-2 text-[12px] text-danger'
            }
          >
            {entry.text}
          </div>
        ))}
        {sending && <div className="mr-auto max-w-[85%] rounded-md border border-border bg-canvas px-3 py-2 text-[12px] text-ink-faint">Думаю…</div>}
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-1.5">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                void send();
              }
            }}
            disabled={capReached}
            placeholder={capReached ? 'Дневной лимит исчерпан' : 'Вопрос…'}
            rows={2}
            className="min-h-[52px] w-full resize-none rounded-md border border-border-strong bg-canvas px-2.5 py-1.5 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={!draft.trim() || sending || capReached}
            aria-label="Отправить"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-white hover:bg-accent-hover disabled:opacity-40"
          >
            <Send size={14} />
          </button>
        </div>
        <p className={capReached ? 'mt-1.5 text-[10.5px] text-danger' : 'mt-1.5 text-[10.5px] text-ink-faint'}>
          {usage
            ? `Потрачено сегодня: ${usage.spent_rub.toFixed(2)} ₽ из ${usage.limit_rub.toFixed(0)} ₽`
            : 'Загружаем расход за сегодня…'}
        </p>
      </div>
    </div>
  );
}
