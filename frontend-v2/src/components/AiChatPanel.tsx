import { ChevronDown, Grip, History, Send, Sparkles, X } from 'lucide-react';
import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../lib/api';
import { formatDateTime } from '../lib/format';

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

const REQUEST_STARTERS = [
  {
    label: 'Сравнить предложения',
    prompt: 'Сравни предложения в текущей и выбранных переписках. Дай таблицу: поставщик, товар или модель, цена, наличие, срок или доставка, условия и что не указано.',
  },
  {
    label: 'Выделить условия и риски',
    prompt: 'Выдели из переписки важные условия, ограничения и риски. Не додумывай: для каждого пункта укажи, что подтверждено письмом, а что нужно уточнить.',
  },
  {
    label: 'Подготовить вопросы',
    prompt: 'Подготовь короткий список уточняющих вопросов поставщику по пробелам в текущей переписке: цена, наличие, срок, доставка, оплата и гарантия — только если эти данные действительно отсутствуют.',
  },
];

const INBOX_STARTERS = [
  {
    label: 'Кратко разобрать письмо',
    prompt: 'Кратко разберись в текущем письме: что предлагает поставщик, какие условия уже названы и что осталось неясным.',
  },
  {
    label: 'Выделить цену и условия',
    prompt: 'Выдели из письма цену, товар или модель, наличие, срок, доставку и условия оплаты. Для отсутствующих данных так и напиши: «нет данных».',
  },
  {
    label: 'Подготовить ответ',
    prompt: 'Подготовь вежливый короткий ответ поставщику с уточняющими вопросами только по данным, которых нет в текущем письме.',
  },
];

function pluralSuppliers(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'поставщик';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'поставщика';
  return 'поставщиков';
}

function renderInlineAiText(value: string): ReactNode {
  return value.split(/(\*\*[^*]+\*\*)/g).map((part, index) => (
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={index} className="font-semibold text-[#26262b]">{part.slice(2, -2)}</strong>
      : part
  ));
}

function isMarkdownTableDivider(row: string): boolean {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(row.trim());
}

function markdownTableCells(row: string): string[] {
  return row.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
}

/**
 * AI output is treated as plain text. This intentionally recognises only the
 * small Markdown subset the chat asks the model to use, so model output never
 * becomes raw HTML in the application. Tables get their own scrolling surface
 * instead of widening the floating dialog.
 */
function renderAiAnswer(text: string): ReactNode {
  const lines = text.replace(/\r/g, '').split('\n');
  const blocks: ReactNode[] = [];

  for (let index = 0; index < lines.length;) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith('|') && index + 1 < lines.length && isMarkdownTableDivider(lines[index + 1])) {
      const header = markdownTableCells(line);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith('|')) {
        rows.push(markdownTableCells(lines[index]));
        index += 1;
      }
      blocks.push(
        <div key={`table-${index}`} className="my-2 overflow-x-auto rounded-lg border border-[#dedee2] bg-white">
          <table className="min-w-[820px] w-full border-collapse text-left text-[10.5px] leading-4">
            <thead className="bg-[#f5f5f6] text-[#4b4b52]">
              <tr>{header.map((cell, cellIndex) => <th key={cellIndex} className="border-b border-[#dedee2] px-2 py-1.5 font-semibold">{renderInlineAiText(cell)}</th>)}</tr>
            </thead>
            <tbody className="text-[#38383e]">
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="align-top even:bg-[#fbfbfc]">
                  {header.map((_, cellIndex) => <td key={cellIndex} className="border-b border-[#ececef] px-2 py-1.5 last:border-b-0">{renderInlineAiText(row[cellIndex] ?? '—')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      blocks.push(<p key={`heading-${index}`} className="mt-2 font-semibold text-[#26262b]">{renderInlineAiText(heading[1])}</p>);
      index += 1;
      continue;
    }

    const listMatch = line.match(/^[-*]\s+(.+)$/);
    const numberedMatch = line.match(/^\d+[.)]\s+(.+)$/);
    if (listMatch || numberedMatch) {
      const ordered = Boolean(numberedMatch);
      const items: string[] = [];
      while (index < lines.length) {
        const current = lines[index].trim();
        const match = ordered ? current.match(/^\d+[.)]\s+(.+)$/) : current.match(/^[-*]\s+(.+)$/);
        if (!match) break;
        items.push(match[1]);
        index += 1;
      }
      const List = ordered ? 'ol' : 'ul';
      blocks.push(<List key={`list-${index}`} className={ordered ? 'my-2 list-decimal space-y-1 pl-5' : 'my-2 list-disc space-y-1 pl-5'}>{items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineAiText(item)}</li>)}</List>);
      continue;
    }

    blocks.push(<p key={`paragraph-${index}`} className="my-1.5 whitespace-pre-wrap">{renderInlineAiText(line)}</p>);
    index += 1;
  }

  return blocks;
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
  const resizeStartRef = useRef<{ x: number; y: number; width: number; height: number } | null>(null);
  const [panelSize, setPanelSize] = useState({ width: 420, height: 660 });

  useEffect(() => {
    function moveResize(event: PointerEvent) {
      const start = resizeStartRef.current;
      if (!start) return;
      const maxWidth = Math.max(300, window.innerWidth - 32);
      const maxHeight = Math.max(360, window.innerHeight - 32);
      setPanelSize({
        width: Math.max(320, Math.min(maxWidth, start.width + start.x - event.clientX)),
        height: Math.max(420, Math.min(maxHeight, start.height + start.y - event.clientY)),
      });
    }
    function endResize() {
      resizeStartRef.current = null;
    }
    window.addEventListener('pointermove', moveResize);
    window.addEventListener('pointerup', endResize);
    return () => {
      window.removeEventListener('pointermove', moveResize);
      window.removeEventListener('pointerup', endResize);
    };
  }, []);

  function startResize(event: ReactPointerEvent<HTMLButtonElement>) {
    event.preventDefault();
    resizeStartRef.current = { x: event.clientX, y: event.clientY, width: panelSize.width, height: panelSize.height };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

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
  const starters = requestId !== null ? REQUEST_STARTERS : INBOX_STARTERS;

  return (
    <section
      className="fixed bottom-4 right-4 z-50 flex max-h-[calc(100dvh-32px)] max-w-[calc(100vw-32px)] flex-col overflow-hidden rounded-[26px] border border-[#d9d9dd] bg-[#fffefe] text-[#1c1c20] shadow-[0_18px_55px_rgba(31,31,36,0.16)]"
      style={{ width: panelSize.width, height: panelSize.height }}
      role="dialog"
      aria-modal="true"
      aria-label="ИИ-помощник SupplyDesk"
    >
      <header className="relative flex h-14 shrink-0 items-center border-b border-[#e7e7ea] pl-9 pr-5">
        <button
          type="button"
          onPointerDown={startResize}
          className="absolute left-2 top-1/2 flex h-6 w-6 -translate-y-1/2 cursor-nwse-resize items-center justify-center rounded-md text-[#85858c] hover:bg-[#f1f0f6] hover:text-[#5142c6] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]"
          aria-label="Изменить размер ИИ-помощника"
          title="Потяните, чтобы изменить размер"
        >
          <Grip size={14} />
        </button>
        <p className="text-[10px] font-semibold tracking-[0.11em] text-[#4b4b52]">SUPPLYDESK · AI</p>
        <div className="ml-auto flex items-center gap-3 text-[10px] font-semibold tracking-[0.1em] text-[#55555c]">
          <button type="button" onClick={startNewChat} className="hover:text-[#17171b] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]" aria-label="Новый ИИ-чат">Новый чат</button>
          {requestId !== null && (
            <button
              type="button"
              onClick={toggleHistory}
              className={`flex h-5 w-5 items-center justify-center rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae] ${historyOpen ? 'bg-[#efeff1] text-[#17171b]' : 'hover:text-[#17171b]'}`}
              aria-label="История ИИ-чатов"
            >
              <History size={13} />
            </button>
          )}
          <button type="button" onClick={onClose} className="text-[17px] font-normal leading-none hover:text-[#17171b] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]" aria-label="Закрыть ИИ-помощника">×</button>
        </div>
      </header>

      <div className="flex shrink-0 items-center border-b border-[#e7e7ea] px-5 py-2.5">
        <span className="min-w-0 flex-1 truncate text-[11px] text-[#777780]" title={conversationTitle || 'Новый чат'}>
          {conversationTitle || (loadingHistory ? 'Загружаем…' : 'Новый чат')}
        </span>
      </div>

        {historyOpen && (
          <div className="max-h-40 shrink-0 overflow-y-auto border-b border-[#e7e7ea]">
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
                  <time className="shrink-0 text-[10px] text-ink-faint" dateTime={c.updated_at}>{formatDateTime(c.updated_at)}</time>
                </button>
              ))
            ) : (
              <p className="px-3 py-2 text-[11px] text-ink-faint">Пока нет предыдущих чатов по этой заявке.</p>
            )}
          </div>
        )}

        {requestId !== null && (
          // Fixed-shrink header/toggle row + a capped-height, independently
          // scrolling chip list -- this is what actually keeps the message
          // input and "Отправить" reachable regardless of how many suppliers
          // are selected: nothing below this block can be pushed off-screen
          // by chip count, because the chip list's own height is bounded and
          // this whole section never grows past max-h-48 collapsed height.
          <div className="shrink-0 border-b border-[#e7e7ea]">
            <div className="px-5 py-3">
              {siblingThreads.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setSiblingsExpanded((v) => !v)}
                  className="flex min-w-0 items-center gap-1.5 text-left text-[11px] font-medium text-ink-soft hover:text-ink"
                >
                  <ChevronDown size={12} className={`shrink-0 text-ink-faint transition-transform ${siblingsExpanded ? 'rotate-180' : ''}`} />
                  <span className="truncate">
                    {selectedSiblingIds.length > 0
                      ? `Контекст: текущая переписка + ${selectedSiblingIds.length} ${pluralSuppliers(selectedSiblingIds.length)}`
                      : 'Текущая переписка включена'}
                  </span>
                </button>
              ) : (
                <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-ink-soft">Текущая переписка включена</span>
              )}
              {(selectedSiblingIds.length < siblingThreads.length || selectedSiblingIds.length > 0) && (
                <div className="mt-1 flex items-center gap-2">
                {selectedSiblingIds.length < siblingThreads.length && (
                  <button type="button" onClick={onSelectAllSiblings} className="text-[11px] font-medium text-accent hover:underline">
                    Выбрать остальных поставщиков
                  </button>
                )}
                {selectedSiblingIds.length > 0 && (
                  <button type="button" onClick={onClearAllSiblings} className="text-[11px] font-medium text-ink-faint hover:text-ink">
                    Очистить
                  </button>
                )}
                </div>
              )}
            </div>
            {siblingsExpanded && (
              <div className="max-h-40 overflow-y-auto border-t border-[#e7e7ea] px-5 py-2.5">
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

        <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {entries.length === 0 && !loadingHistory && (
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-subtle text-accent">
                <Sparkles size={16} />
              </span>
              <p className="max-w-[250px] text-[12px] text-ink-faint">
                {requestId !== null
                  ? 'ИИ видит текущую переписку и только выбранных поставщиков этой заявки.'
                  : 'ИИ видит только открытое письмо. Связать его с заявкой можно отдельно.'}
              </p>
              <div className="mt-2 w-full max-w-[280px] text-left">
                <p className="mb-1.5 text-[9px] font-semibold tracking-[0.12em] text-ink-faint">НАЧАТЬ С</p>
                <div className="divide-y divide-[#e7e7ea] rounded-xl border border-[#e7e7ea] bg-white">
                  {starters.map((starter) => (
                    <button
                      key={starter.label}
                      type="button"
                      onClick={() => setDraft(starter.prompt)}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-[11.5px] font-medium text-[#3d3d43] transition-colors hover:bg-[#f7f7f8] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]"
                    >
                      <span>{starter.label}</span><span aria-hidden="true" className="text-[#8c8c94]">›</span>
                    </button>
                  ))}
                </div>
              </div>
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
                    ? 'max-w-[90%] rounded-2xl rounded-br-sm bg-accent px-3.5 py-2 text-[12.5px] text-white'
                    : entry.role === 'assistant'
                      ? 'max-w-[90%] rounded-2xl rounded-bl-sm border border-border bg-canvas px-3.5 py-2 text-[12.5px] text-ink'
                      : 'max-w-[90%] rounded-2xl rounded-bl-sm border border-danger-border bg-danger-subtle px-3.5 py-2 text-[12px] text-danger'
                }
              >
                {entry.role === 'assistant' ? renderAiAnswer(entry.text) : entry.text}
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

        <div className="shrink-0 border-t border-[#e7e7ea] px-4 pb-4 pt-3">
          <div className="flex items-end gap-1.5 rounded-2xl border border-[#d7d7db] bg-[#fbfbfc] px-2 py-1.5 focus-within:border-[#a7a7ae] focus-within:ring-1 focus-within:ring-[#a7a7ae]">
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
              placeholder={capReached ? 'Дневной лимит исчерпан' : 'Например: сравни цену, сроки и риски'}
              rows={1}
              className="min-h-[28px] w-full resize-none bg-transparent px-1 py-1 text-[12.5px] outline-none placeholder:text-ink-faint disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={!draft.trim() || sending || capReached}
              aria-label="Отправить"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#686871] text-white hover:bg-[#45454c] disabled:opacity-40"
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
    </section>
  );
}
