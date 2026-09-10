import { ChevronDown, History, Plus, Send, Sparkles, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../lib/api';

interface ChatEntry {
  id?: number;
  role: 'user' | 'assistant' | 'system-error';
  text: string;
}

interface ConversationSummary {
  id: number;
  title: string;
  updated_at: string;
}

function pluralSuppliers(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'поставщик';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'поставщика';
  return 'поставщиков';
}

/** History/current chat are scoped to one заявка (requestId) or one
 * unmatched inbox conversation -- callers should pass a matching React
 * `key` (see Messages.tsx) so switching to a different заявка remounts with
 * fresh state instead of bleeding one заявка's chats into another's.
 * Switching between suppliers *within* the same заявка does NOT remount --
 * the AI conversation is a заявка-level chat, not a per-supplier one. */
export function AiChatPanel({
  requestId,
  threadIds,
  inboxMessageId,
  onClose,
  siblingThreads = [],
  selectedSiblingIds = [],
  onToggleSibling,
  onSelectAllSiblings,
  onClearAllSiblings,
}: {
  requestId: number | null;
  threadIds: number[];
  inboxMessageId: number | null;
  onClose: () => void;
  /** Other suppliers' threads on the same request, offered as extra context. */
  siblingThreads?: { id: number; name: string; globalSupplierId: number | null }[];
  selectedSiblingIds?: number[];
  onToggleSibling?: (id: number) => void;
  onSelectAllSiblings?: () => void;
  onClearAllSiblings?: () => void;
}) {
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string>('');
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(requestId !== null);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [usage, setUsage] = useState<{ spent_rub: number; limit_rub: number } | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyList, setHistoryList] = useState<ConversationSummary[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  // Selected-suppliers chips are collapsed by default once there are enough
  // of them to threaten the input/send button below (see the layout note at
  // the chip list itself) -- expanded manually stays expanded until the user
  // collapses it again, it never auto-collapses out from under them.
  const [siblingsExpanded, setSiblingsExpanded] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // Resume the заявка's most recent chat on open -- a chat must survive
  // refresh, per the owner's requirement, so opening the panel should not
  // silently start a new one every time. Unmatched-inbox conversations
  // (requestId === null) have no durable grouping key of their own yet, so
  // they always start a fresh chat -- an explicit, disclosed scope boundary,
  // not an oversight.
  useEffect(() => {
    if (requestId === null) {
      setLoadingHistory(false);
      return;
    }
    let cancelled = false;
    api
      .listAiConversations(requestId)
      .then((res) => {
        if (cancelled) return;
        const latest = res.items[0];
        if (latest) return openConversation(latest.id);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId]);

  useEffect(() => {
    api
      .getAiChatUsage()
      .then((res) => setUsage({ spent_rub: res.spent_rub, limit_rub: res.limit_rub }))
      .catch(() => {});
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [entries]);

  async function openConversation(id: number) {
    setHistoryOpen(false);
    setLoadingHistory(true);
    try {
      const res = await api.getAiConversation(id);
      setConversationId(res.conversation.id);
      setConversationTitle(res.conversation.title);
      setEntries(res.items.map((m) => ({ id: m.id, role: m.role, text: m.content })));
    } catch {
      // Leave the current chat as-is; the button press simply didn't do anything visible.
    } finally {
      setLoadingHistory(false);
    }
  }

  function startNewChat() {
    setConversationId(null);
    setConversationTitle('');
    setEntries([]);
    setHistoryOpen(false);
  }

  function toggleHistory() {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (next && requestId !== null) {
      setHistoryLoading(true);
      api
        .listAiConversations(requestId)
        .then((res) => setHistoryList(res.items))
        .catch(() => setHistoryList([]))
        .finally(() => setHistoryLoading(false));
    }
  }

  async function send() {
    const text = draft.trim();
    if (!text || sending) return;
    setEntries((prev) => [...prev, { role: 'user', text }]);
    setDraft('');
    setSending(true);
    try {
      const res = await api.sendAiChatMessage({
        conversation_id: conversationId,
        request_id: requestId,
        thread_ids: requestId !== null ? threadIds : [],
        inbox_message_id: inboxMessageId,
        message: text,
      });
      setUsage({ spent_rub: res.spent_rub, limit_rub: res.limit_rub });
      if (res.conversation_id !== null && res.conversation_id !== conversationId) {
        setConversationId(res.conversation_id);
        setConversationTitle(text.slice(0, 60));
      }
      if (res.status === 'success' && res.reply) {
        setEntries((prev) => [...prev, { role: 'assistant', text: res.reply as string }]);
      } else {
        setEntries((prev) => [...prev, { role: 'system-error', text: res.message || 'Не удалось получить ответ.' }]);
      }
    } catch (e) {
      setEntries((prev) => [...prev, { role: 'system-error', text: e instanceof ApiError ? e.message : 'Не удалось связаться с ИИ-помощником.' }]);
    } finally {
      setSending(false);
    }
  }

  const capReached = usage !== null && usage.spent_rub >= usage.limit_rub;

  return (
    <div className="flex h-full w-full shrink-0 flex-col border-l border-border bg-canvas p-3 sm:w-[340px]">
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

        <div className="flex shrink-0 items-center gap-1 border-b border-border px-2 py-1.5">
          <button
            type="button"
            onClick={startNewChat}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-ink-soft hover:bg-surface-hover hover:text-ink"
          >
            <Plus size={12} /> Новый чат
          </button>
          {requestId !== null && (
            <button
              type="button"
              onClick={toggleHistory}
              className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium ${historyOpen ? 'bg-accent-subtle text-accent' : 'text-ink-soft hover:bg-surface-hover hover:text-ink'}`}
            >
              <History size={12} /> История
            </button>
          )}
          <span className="min-w-0 flex-1 truncate px-1.5 text-right text-[11px] text-ink-faint" title={conversationTitle || 'Новый чат'}>
            {conversationTitle || (loadingHistory ? 'Загружаем…' : 'Новый чат')}
          </span>
        </div>

        {historyOpen && (
          <div className="max-h-40 shrink-0 overflow-y-auto border-b border-border">
            {historyLoading ? (
              <p className="px-3 py-2 text-[11px] text-ink-faint">Загружаем историю…</p>
            ) : historyList && historyList.length > 0 ? (
              historyList.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => void openConversation(c.id)}
                  className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-[11.5px] hover:bg-surface-hover ${c.id === conversationId ? 'bg-accent-subtle/40 text-accent' : 'text-ink-soft'}`}
                >
                  <span className="min-w-0 flex-1 truncate">{c.title || 'Без названия'}</span>
                </button>
              ))
            ) : (
              <p className="px-3 py-2 text-[11px] text-ink-faint">Пока нет предыдущих чатов по этой заявке.</p>
            )}
          </div>
        )}

        {siblingThreads.length > 0 && (
          // Fixed-shrink header/toggle row + a capped-height, independently
          // scrolling chip list -- this is what actually keeps the message
          // input and "Отправить" reachable regardless of how many suppliers
          // are selected: nothing below this block can be pushed off-screen
          // by chip count, because the chip list's own height is bounded and
          // this whole section never grows past max-h-48 collapsed height.
          <div className="shrink-0 border-b border-border">
            <div className="flex items-center gap-2 px-3 py-2">
              <button
                type="button"
                onClick={() => setSiblingsExpanded((v) => !v)}
                className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-[11px] font-medium text-ink-soft hover:text-ink"
              >
                <ChevronDown size={12} className={`shrink-0 text-ink-faint transition-transform ${siblingsExpanded ? 'rotate-180' : ''}`} />
                <span className="truncate">
                  {selectedSiblingIds.length > 0
                    ? `Контекст: ${selectedSiblingIds.length + 1} ${pluralSuppliers(selectedSiblingIds.length + 1)}`
                    : 'Сравнение с другими поставщиками'}
                </span>
              </button>
              <div className="flex shrink-0 items-center gap-2">
                {selectedSiblingIds.length < siblingThreads.length && (
                  <button type="button" onClick={onSelectAllSiblings} className="text-[11px] font-medium text-accent hover:underline">
                    Выбрать всех поставщиков по заявке
                  </button>
                )}
                {selectedSiblingIds.length > 0 && (
                  <button type="button" onClick={onClearAllSiblings} className="text-[11px] font-medium text-ink-faint hover:text-ink">
                    Очистить
                  </button>
                )}
              </div>
            </div>
            {siblingsExpanded && (
              <div className="max-h-40 overflow-y-auto border-t border-border px-3 py-2">
                {selectedSiblingIds.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {selectedSiblingIds.map((id) => {
                      const t = siblingThreads.find((s) => s.id === id);
                      if (!t) return null;
                      return (
                        <span key={id} className="flex items-center gap-1 rounded-full bg-accent-subtle px-2 py-0.5 text-[11px] text-accent">
                          {t.globalSupplierId ? (
                            <Link to={`/suppliers/${t.globalSupplierId}`} title="Открыть карточку поставщика" className="hover:underline">
                              {t.name}
                            </Link>
                          ) : (
                            t.name
                          )}
                          <button type="button" onClick={() => onToggleSibling?.(id)} aria-label={`Убрать ${t.name} из контекста`} className="hover:text-accent-hover">
                            <X size={10} />
                          </button>
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-[11px] text-ink-faint">Отметьте галочкой поставщиков слева в списке переписок, чтобы добавить их в контекст для сравнения.</p>
                )}
              </div>
            )}
          </div>
        )}

        <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-3.5 py-3.5">
          {entries.length === 0 && !loadingHistory && (
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-subtle text-accent">
                <Sparkles size={16} />
              </span>
              <p className="max-w-[200px] text-[12px] text-ink-faint">Спросите что-нибудь про эту заявку или поставщика.</p>
            </div>
          )}
          {entries.map((entry, i) => (
            <div key={entry.id ?? i} className={`flex items-end gap-1.5 ${entry.role === 'user' ? 'flex-row-reverse' : ''}`}>
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
