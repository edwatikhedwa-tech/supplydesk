import { ChevronDown, Plus, Send, Sparkles, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

interface ChatEntry {
  role: 'user' | 'assistant' | 'system-error';
  text: string;
}

const STORAGE_PREFIX = 'supplydesk:ai-chat:';

function loadEntries(storageKey: string): ChatEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + storageKey);
    return raw ? (JSON.parse(raw) as ChatEntry[]) : [];
  } catch {
    return [];
  }
}

/** `storageKey` identifies the conversation (thread id / unmatched message
 * id) -- callers should also pass it as this component's React `key` so
 * switching conversations remounts with fresh state instead of bleeding one
 * thread's chat into another's. */
export function AiChatPanel({
  context,
  storageKey,
  onClose,
  siblingThreads = [],
  selectedSiblingIds = [],
  onToggleSibling,
}: {
  context: string;
  storageKey: string;
  onClose: () => void;
  /** Other suppliers' threads on the same request, offered as extra context. */
  siblingThreads?: { id: number; name: string }[];
  selectedSiblingIds?: number[];
  onToggleSibling?: (id: number) => void;
}) {
  const [entries, setEntries] = useState<ChatEntry[]>(() => loadEntries(storageKey));
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [usage, setUsage] = useState<{ spent_rub: number; limit_rub: number } | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!pickerOpen) return;
    function onDocClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) setPickerOpen(false);
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [pickerOpen]);

  useEffect(() => {
    try {
      if (entries.length > 0) localStorage.setItem(STORAGE_PREFIX + storageKey, JSON.stringify(entries));
      else localStorage.removeItem(STORAGE_PREFIX + storageKey);
    } catch {
      // Best-effort persistence -- a full/blocked localStorage shouldn't break the chat itself.
    }
  }, [entries, storageKey]);

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
    <div className="flex w-[340px] shrink-0 flex-col border-l border-border bg-canvas p-3">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
        <div className="flex items-center justify-between border-b border-border bg-gradient-to-r from-accent-subtle/60 to-transparent px-4 py-3">
          <span className="flex items-center gap-2 text-[13px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent text-white">
              <Sparkles size={12} />
            </span>
            ИИ-помощник
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть ИИ-помощника"
            className="flex h-6 w-6 items-center justify-center rounded-full text-ink-muted hover:bg-surface-hover hover:text-ink"
          >
            <X size={14} />
          </button>
        </div>

        {siblingThreads.length > 0 && (
          <div className="relative border-b border-border px-3 py-2" ref={pickerRef}>
            <div className="flex flex-wrap items-center gap-1.5">
              {selectedSiblingIds.map((id) => {
                const t = siblingThreads.find((s) => s.id === id);
                if (!t) return null;
                return (
                  <span key={id} className="flex items-center gap-1 rounded-full bg-accent-subtle px-2 py-0.5 text-[11px] text-accent">
                    {t.name}
                    <button type="button" onClick={() => onToggleSibling?.(id)} aria-label={`Убрать ${t.name} из контекста`} className="hover:text-accent-hover">
                      <X size={10} />
                    </button>
                  </span>
                );
              })}
              <button
                type="button"
                onClick={() => setPickerOpen((v) => !v)}
                className="flex items-center gap-1 rounded-full border border-dashed border-border-strong px-2 py-0.5 text-[11px] text-ink-muted hover:border-accent hover:text-accent"
              >
                <Plus size={10} />
                Сравнить с поставщиком
                <ChevronDown size={10} />
              </button>
            </div>

            {pickerOpen && (
              <div className="absolute left-3 top-[calc(100%+2px)] z-30 max-h-[200px] w-[240px] overflow-y-auto rounded-lg border border-border bg-surface py-1 shadow-lg">
                {siblingThreads.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onToggleSibling?.(t.id)}
                    className="flex w-full items-center justify-between px-3 py-1.5 text-left text-[12px] hover:bg-surface-hover"
                  >
                    <span className="truncate text-ink">{t.name}</span>
                    {selectedSiblingIds.includes(t.id) && <span className="text-accent">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-3.5 py-3.5">
          {entries.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-subtle text-accent">
                <Sparkles size={16} />
              </span>
              <p className="max-w-[200px] text-[12px] text-ink-faint">Спросите что-нибудь про эту заявку или поставщика.</p>
            </div>
          )}
          {entries.map((entry, i) => (
            <div key={i} className={`flex items-end gap-1.5 ${entry.role === 'user' ? 'flex-row-reverse' : ''}`}>
              {entry.role !== 'user' && (
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-subtle text-accent">
                  <Sparkles size={11} />
                </span>
              )}
              <div
                className={
                  entry.role === 'user'
                    ? 'max-w-[78%] rounded-2xl rounded-br-sm bg-accent px-3.5 py-2 text-[12.5px] text-white'
                    : entry.role === 'assistant'
                      ? 'max-w-[78%] rounded-2xl rounded-bl-sm border border-border bg-canvas px-3.5 py-2 text-[12.5px] text-ink'
                      : 'max-w-[78%] rounded-2xl rounded-bl-sm border border-danger-border bg-danger-subtle px-3.5 py-2 text-[12px] text-danger'
                }
              >
                {entry.text}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex items-end gap-1.5">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-subtle text-accent">
                <Sparkles size={11} />
              </span>
              <div className="rounded-2xl rounded-bl-sm border border-border bg-canvas px-3.5 py-2 text-[12px] text-ink-faint">Думаю…</div>
            </div>
          )}
        </div>

        <div className="border-t border-border p-3">
          <div className="flex items-end gap-1.5 rounded-xl border border-border-strong bg-canvas px-2 py-1.5 focus-within:border-accent focus-within:ring-1 focus-within:ring-accent-border">
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
              rows={1}
              className="min-h-[28px] w-full resize-none bg-transparent px-1 py-1 text-[12.5px] outline-none placeholder:text-ink-faint disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={!draft.trim() || sending || capReached}
              aria-label="Отправить"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-white hover:bg-accent-hover disabled:opacity-40"
            >
              <Send size={13} />
            </button>
          </div>
          <p className={capReached ? 'mt-1.5 text-[10.5px] text-danger' : 'mt-1.5 text-[10.5px] text-ink-faint'}>
            {usage
              ? `Потрачено сегодня: ${usage.spent_rub.toFixed(2)} ₽ из ${usage.limit_rub.toFixed(0)} ₽`
              : 'Загружаем расход за сегодня…'}
          </p>
        </div>
      </div>
    </div>
  );
}
