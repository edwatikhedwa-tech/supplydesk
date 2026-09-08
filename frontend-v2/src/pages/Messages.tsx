import clsx from 'clsx';
import {
  ArrowDownLeft,
  ArrowUpRight,
  Ban,
  CheckCheck,
  ChevronRight,
  Clock3,
  Inbox,
  Link2,
  Paperclip,
  Send,
  Sparkles,
  SquareCheck,
  StickyNote,
  Truck,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { useSearchParams } from 'react-router-dom';
import { AiChatPanel } from '../components/AiChatPanel';
import { LogisticsQuoteModal } from '../components/LogisticsQuoteModal';
import { ManualLinkModal } from '../components/ManualLinkModal';
import { NotesPanel } from '../components/NotesPanel';
import { TasksPanel } from '../components/TasksPanel';
import { PageHeader } from '../components/shell/PageHeader';
import { Avatar } from '../components/ui/Avatar';
import { Badge, type Tone } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';
import { threadResponseStatus, messageSenderName, type ResponseStatus } from '../lib/derive';
import { formatCompanyName, formatDateTime, formatRelativeTime } from '../lib/format';
import type { InboxConversation, MailMessage, ThreadSummary } from '../lib/types';
import { useApiData } from '../lib/useApiData';

type Selection = { type: 'thread'; id: number } | { type: 'unmatched'; id: number } | null;
type AsyncState<T> = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: T };

const AI_CONTEXT_PER_MESSAGE_LIMIT = 700;
// Total transcript budget, not per-message -- keeps a long back-and-forth from
// blowing past the cheap model's context and the per-user daily spend cap.
const AI_CONTEXT_TOTAL_BUDGET = 3500;

function trimBody(text: string | null, limit = AI_CONTEXT_PER_MESSAGE_LIMIT): string {
  if (!text) return '';
  const clean = text.trim().replace(/\s+/g, ' ');
  return clean.length > limit ? `${clean.slice(0, limit)}…` : clean;
}

// Compact per-thread budget when several suppliers' conversations are added
// to context at once -- a full transcript per thread would blow past both
// the cheap model's context and the daily spend cap once more than one or
// two are selected.
const AI_CONTEXT_EXTRA_THREAD_BUDGET = 500;

/** Feeds the AI assistant the real conversation, not just the request/supplier
 * names -- without it the model has nothing concrete to reason about and
 * falls back to guessing from the request's internal title. Walks newest to
 * oldest so a long thread keeps its most recent messages when it must be
 * truncated to fit the budget, then restores chronological order.
 *
 * `extraThreads` lets the user pull in other suppliers' conversations on the
 * same request for comparison (e.g. "who quoted the lowest price?") --
 * summarized to the last message only, to keep cost bounded regardless of
 * how many are added. */
function buildAiContext(
  activeThread: ThreadSummary | null,
  messagesState: AsyncState<MailMessage[]>,
  activeUnmatchedId: number | null,
  conversationState: AsyncState<InboxConversation | null>,
  extraThreads: { thread: ThreadSummary; messages: MailMessage[] }[] = [],
): string {
  let mainContext = '';
  if (activeThread) {
    const header = `Заявка «${activeThread.request_name}» (это просто название заявки в системе, не техническое требование), поставщик ${formatCompanyName(activeThread.supplier_name)}.`;
    if (messagesState.status === 'ready' && messagesState.data.length > 0) {
      const lines: string[] = [];
      let used = 0;
      for (let i = messagesState.data.length - 1; i >= 0; i--) {
        const m = messagesState.data[i];
        const who = m.direction === 'outbound' ? 'Мы' : 'Поставщик';
        const line = `${who} (${formatDateTime(m.sent_at ?? m.created_at)}): ${trimBody(m.body_text)}`;
        if (used + line.length > AI_CONTEXT_TOTAL_BUDGET && lines.length > 0) break;
        lines.unshift(line);
        used += line.length;
      }
      mainContext = `${header}\nПереписка целиком, от старых сообщений к новым:\n${lines.join('\n\n')}`;
    } else {
      mainContext = header;
    }
  } else if (activeUnmatchedId && conversationState.status === 'ready' && conversationState.data) {
    const c = conversationState.data;
    mainContext = `Письмо без привязки к заявке от ${c.from_email}, тема «${c.subject}»:\n${trimBody(c.body_text)}`;
  }

  if (extraThreads.length === 0) return mainContext;

  const extraBlocks = extraThreads
    .filter((e) => e.messages.length > 0)
    .map((e) => {
      const last = e.messages[e.messages.length - 1];
      const who = last.direction === 'outbound' ? 'Мы' : 'Поставщик';
      return `— ${formatCompanyName(e.thread.supplier_name)}: последнее сообщение (${who}, ${formatDateTime(last.sent_at ?? last.created_at)}): ${trimBody(last.body_text, AI_CONTEXT_EXTRA_THREAD_BUDGET)}`;
    });
  if (extraBlocks.length === 0) return mainContext;
  return `${mainContext}\n\nДля сравнения — другие поставщики по этой же заявке:\n${extraBlocks.join('\n')}`;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Wraps every case-insensitive match of `query` in the searched-for message's
 * body with <mark>, so landing on a search result shows exactly what matched. */
function highlightText(text: string, query: string) {
  const q = query.trim();
  if (!q) return text;
  const parts = text.split(new RegExp(`(${escapeRegExp(q)})`, 'ig'));
  if (parts.length === 1) return text;
  return parts.map((part, i) =>
    part.toLowerCase() === q.toLowerCase() ? (
      <mark key={i} className="rounded-sm bg-warning-subtle text-ink">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

const responseTone: Record<ResponseStatus, Tone> = { none: 'neutral', waiting: 'warning', answered: 'success' };
const responseLabel: Record<ResponseStatus, string> = { none: 'Не отправлено', waiting: 'Ожидаем ответ', answered: 'Есть ответ' };

type ThreadFilter = 'all' | 'answered' | 'waiting' | 'unread';
const THREAD_FILTER_LABELS: Record<ThreadFilter, string> = {
  all: 'Все',
  answered: 'Есть ответ',
  waiting: 'Ждём ответа',
  unread: 'Непрочитанные',
};
function matchesThreadFilter(t: ThreadSummary, filter: ThreadFilter): boolean {
  switch (filter) {
    case 'answered':
      return threadResponseStatus(t) === 'answered';
    case 'waiting':
      return threadResponseStatus(t) === 'waiting';
    case 'unread':
      return t.unread_count > 0;
    default:
      return true;
  }
}

export function Messages() {
  const { user } = useAuth();
  const threadsState = useApiData(() => api.listThreads().then((r) => r.items), []);
  const requestsState = useApiData(() => api.listRequests().then((r) => r.items), []);
  const unmatchedState = useApiData(() => api.listInboxPreview().then((r) => r.items), []);

  const threads = threadsState.status === 'ready' ? threadsState.data : [];
  const deadlineByRequestId = useMemo(() => {
    const map = new Map<number, string>();
    if (requestsState.status === 'ready') for (const r of requestsState.data) map.set(r.id, r.deadline);
    return map;
  }, [requestsState]);

  const groups = useMemo(() => {
    const byRequest = new Map<number, { request_id: number; request_name: string; threads: ThreadSummary[] }>();
    for (const t of threads) {
      if (!byRequest.has(t.request_id)) byRequest.set(t.request_id, { request_id: t.request_id, request_name: t.request_name, threads: [] });
      byRequest.get(t.request_id)!.threads.push(t);
    }
    return [...byRequest.values()].sort(
      (a, b) => new Date(b.threads[0]?.last_message_at ?? 0).getTime() - new Date(a.threads[0]?.last_message_at ?? 0).getTime(),
    );
  }, [threads]);

  const [threadFilter, setThreadFilter] = useState<ThreadFilter>('all');
  const threadFilterCounts = useMemo(
    () => ({
      all: threads.length,
      answered: threads.filter((t) => threadResponseStatus(t) === 'answered').length,
      waiting: threads.filter((t) => threadResponseStatus(t) === 'waiting').length,
      unread: threads.filter((t) => t.unread_count > 0).length,
    }),
    [threads],
  );
  const filteredGroups = useMemo(() => {
    if (threadFilter === 'all') return groups;
    return groups
      .map((g) => ({ ...g, threads: g.threads.filter((t) => matchesThreadFilter(t, threadFilter)) }))
      .filter((g) => g.threads.length > 0);
  }, [groups, threadFilter]);

  const [searchParams, setSearchParams] = useSearchParams();
  const requestedThreadIdParam = searchParams.get('thread');
  const requestedRequestId = searchParams.get('request');
  const requestedSupplierId = searchParams.get('supplier');
  // Captured once on mount (functional initial state), not read on every
  // render -- selectionInitialized's effect below clears the URL's search
  // params shortly after mount, so reading them live would lose the value.
  const [pendingHighlight] = useState<{ messageId: number; query: string } | null>(() => {
    const highlight = searchParams.get('highlight');
    return highlight ? { messageId: Number(highlight), query: searchParams.get('q') ?? '' } : null;
  });
  const messageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  // The request-detail page only knows (request_id, supplier_id), not the
  // thread's own id — resolve it here once threads are loaded, so callers
  // don't need to know mail_threads.id to deep-link into a conversation.
  const requestedThreadId =
    requestedThreadIdParam ??
    (requestedRequestId && requestedSupplierId
      ? threads.find((t) => t.request_id === Number(requestedRequestId) && t.supplier_id === Number(requestedSupplierId))?.id.toString() ?? null
      : null);

  const [expanded, setExpanded] = useState<Set<number> | null>(null);
  useEffect(() => {
    if (expanded === null && groups.length > 0) {
      const withUnread = groups.filter((g) => g.threads.some((t) => t.unread_count > 0)).map((g) => g.request_id);
      const requested = requestedThreadId ? groups.find((g) => g.threads.some((t) => t.id === Number(requestedThreadId))) : null;
      setExpanded(new Set(requested ? [...withUnread, requested.request_id] : withUnread));
    }
  }, [groups, expanded, requestedThreadId]);

  const [selection, setSelection] = useState<Selection>(null);
  const [selectionInitialized, setSelectionInitialized] = useState(false);
  useEffect(() => {
    if (selectionInitialized || threads.length === 0) return;
    const requested = requestedThreadId ? threads.find((t) => t.id === Number(requestedThreadId)) : null;
    const target = requested ?? threads.find((t) => t.unread_count > 0) ?? threads[0];
    setSelection({ type: 'thread', id: target.id });
    setSelectionInitialized(true);
    if (requestedThreadId) setSearchParams({}, { replace: true });
  }, [threads, selectionInitialized, requestedThreadId, setSearchParams]);

  const [draft, setDraft] = useState('');
  const [logisticsOpen, setLogisticsOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiExtraThreadIds, setAiExtraThreadIds] = useState<number[]>([]);
  const [aiExtraMessages, setAiExtraMessages] = useState<Record<number, MailMessage[]>>({});
  const draftRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = draftRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 320)}px`;
  }, [draft]);

  const activeThread = selection?.type === 'thread' ? threads.find((t) => t.id === selection.id) ?? null : null;
  const activeDeadline = activeThread ? deadlineByRequestId.get(activeThread.request_id) ?? '' : '';
  const activeUnmatchedId = selection?.type === 'unmatched' ? selection.id : null;

  const messagesState = useApiData(
    () => (activeThread ? api.threadMessages(activeThread.request_id, activeThread.supplier_id).then((r) => r.items) : Promise.resolve([])),
    [activeThread?.id],
  );
  const conversationState = useApiData(
    () => (activeUnmatchedId ? api.inboxConversation(activeUnmatchedId) : Promise.resolve(null)),
    [activeUnmatchedId],
  );
  const noteState = useApiData(
    () => (activeThread ? api.getThreadNote(activeThread.request_id, activeThread.supplier_id).then((r) => r.note) : Promise.resolve('')),
    [activeThread?.request_id, activeThread?.supplier_id],
  );
  const hasNote = noteState.status === 'ready' && noteState.data.trim() !== '';

  // Other suppliers' threads on this same request -- candidates the AI panel
  // can pull in for cross-supplier comparison ("who quoted lowest?").
  const siblingThreads = activeThread ? threads.filter((t) => t.request_id === activeThread.request_id && t.id !== activeThread.id) : [];

  useEffect(() => {
    setAiExtraThreadIds([]);
    setAiExtraMessages({});
  }, [activeThread?.id]);

  useEffect(() => {
    for (const id of aiExtraThreadIds) {
      if (aiExtraMessages[id]) continue;
      const t = threads.find((x) => x.id === id);
      if (!t) continue;
      api
        .threadMessages(t.request_id, t.supplier_id)
        .then((r) => setAiExtraMessages((prev) => ({ ...prev, [id]: r.items })))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiExtraThreadIds, threads]);

  const aiExtraThreadsForContext = aiExtraThreadIds
    .map((id) => {
      const thread = threads.find((t) => t.id === id);
      return thread ? { thread, messages: aiExtraMessages[id] ?? [] } : null;
    })
    .filter((x): x is { thread: ThreadSummary; messages: MailMessage[] } => x !== null);

  useEffect(() => {
    if (!pendingHighlight || messagesState.status !== 'ready') return;
    const el = messageRefs.current.get(pendingHighlight.messageId);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [pendingHighlight, messagesState]);

  const suggestionsState = useApiData(
    () => (activeUnmatchedId ? api.inboxSuggestions(activeUnmatchedId).then((r) => r.items) : Promise.resolve([])),
    [activeUnmatchedId],
  );

  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);
  const [manualLinkOpen, setManualLinkOpen] = useState(false);
  const [ignoring, setIgnoring] = useState(false);
  const [confirmingIgnore, setConfirmingIgnore] = useState(false);
  const [unmatchedDraft, setUnmatchedDraft] = useState('');
  const [unmatchedReplyError, setUnmatchedReplyError] = useState('');
  const [sendingUnmatchedReply, setSendingUnmatchedReply] = useState(false);

  function toggleGroup(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev ?? []);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectThread(threadId: number) {
    setSelection({ type: 'thread', id: threadId });
  }

  async function linkSuggestion() {
    if (!activeUnmatchedId || suggestionsState.status !== 'ready' || suggestionsState.data.length === 0) return;
    const best = suggestionsState.data[0];
    setLinking(true);
    setLinkError(null);
    try {
      await api.attachInboxMessage({ inbox_message_id: activeUnmatchedId, request_id: best.request_id, supplier_id: best.supplier_id });
      unmatchedState.reload();
      threadsState.reload();
      setSelection(null);
    } catch {
      setLinkError('Не удалось связать письмо с заявкой.');
    } finally {
      setLinking(false);
    }
  }

  async function ignoreUnmatched() {
    if (!activeUnmatchedId) return;
    setIgnoring(true);
    setLinkError(null);
    try {
      await api.ignoreInboxMessage(activeUnmatchedId);
      unmatchedState.reload();
      setSelection(null);
    } catch (e) {
      setLinkError(e instanceof ApiError ? e.message : 'Не удалось скрыть письмо.');
    } finally {
      setIgnoring(false);
      setConfirmingIgnore(false);
    }
  }
  useEffect(() => setConfirmingIgnore(false), [activeUnmatchedId]);

  async function sendUnmatchedReply() {
    if (!activeUnmatchedId || conversationState.status !== 'ready' || !conversationState.data || !unmatchedDraft.trim()) return;
    setSendingUnmatchedReply(true);
    setUnmatchedReplyError('');
    try {
      await api.replyToInbox({
        inbox_message_id: activeUnmatchedId,
        subject: conversationState.data.subject.startsWith('Re:') ? conversationState.data.subject : `Re: ${conversationState.data.subject}`,
        body_text: unmatchedDraft.trim(),
      });
      setUnmatchedDraft('');
      conversationState.reload();
    } catch (e) {
      setUnmatchedReplyError(e instanceof ApiError ? e.message : 'Не удалось отправить ответ.');
    } finally {
      setSendingUnmatchedReply(false);
    }
  }

  async function sendReply() {
    if (!activeThread || !draft.trim()) return;
    const subject = messagesState.status === 'ready' && messagesState.data.length > 0 ? `Re: ${messagesState.data[0].subject}` : activeThread.subject;
    await api.sendMail({
      request_id: activeThread.request_id,
      supplier: { id: activeThread.supplier_id, email: activeThread.supplier_email },
      subject,
      body_text: draft.trim(),
    });
    setDraft('');
    messagesState.reload();
    threadsState.reload();
  }

  const ownerName = user?.display_name ?? 'Вы';
  const unmatched = unmatchedState.status === 'ready' ? unmatchedState.data : [];
  // "За неделю" -- unread and received in the last 7 days. Reading a message
  // or ignoring it (both change what the backend returns) drops it out on
  // the next reload, so once everything from the week has been looked at or
  // dismissed the section is empty, not just uncounted.
  const weeklyUnmatched = useMemo(() => {
    const cutoff = Date.now() - 7 * 86400000;
    return unmatched.filter((m) => m.unread && new Date(m.received_at).getTime() >= cutoff);
  }, [unmatched]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader title="Сообщения" />
      <div className="flex min-h-0 flex-1">
        <Group orientation="horizontal" className="flex flex-1">
          <Panel defaultSize="30%" minSize="22%" maxSize="42%" className="flex min-w-0 flex-col border-r border-border">
            <div className="flex items-center gap-1 border-b border-border p-2">
              <button className="flex-1 rounded-md bg-accent-subtle px-2.5 py-1.5 text-[12.5px] font-medium text-accent">По заявкам</button>
              <button disabled className="flex-1 cursor-not-allowed rounded-md px-2.5 py-1.5 text-[12.5px] font-medium text-ink-faint" title="Полный режим почты — скоро">
                Почта
              </button>
            </div>

            {threadsState.status === 'loading' ? (
              <LoadingState label="Загружаем переписку…" />
            ) : threadsState.status === 'error' ? (
              <ErrorState message={threadsState.message} onRetry={threadsState.reload} />
            ) : (
              <div className="overflow-y-auto">
                <button
                  onClick={() => weeklyUnmatched[0] && setSelection({ type: 'unmatched', id: weeklyUnmatched[0].id })}
                  className="flex w-full items-center gap-2.5 border-b border-border px-3 py-2.5 text-left hover:bg-surface-hover"
                >
                  <Inbox size={14} className="text-ink-muted" />
                  <span className="flex-1 text-[12.5px] font-medium text-ink">Новые письма без заявки за неделю</span>
                  {weeklyUnmatched.length > 0 && <Badge tone="accent">{weeklyUnmatched.length}</Badge>}
                </button>
                {selection?.type === 'unmatched' &&
                  weeklyUnmatched.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setSelection({ type: 'unmatched', id: m.id })}
                      className={
                        'flex w-full items-start gap-2 border-b border-border py-2 pl-8 pr-3 text-left hover:bg-surface-hover ' +
                        (activeUnmatchedId === m.id ? 'border-l-2 border-l-accent bg-accent-subtle/40' : '')
                      }
                    >
                      {m.unread && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent ring-4 ring-accent/20" title="Не прочитано" />}
                      <div className="min-w-0 flex-1">
                        <p className={clsx('truncate text-[12px]', m.unread ? 'font-semibold text-ink' : 'font-medium text-ink-soft')}>{m.subject}</p>
                        <p className="truncate text-[11px] text-ink-muted">{m.from_email}</p>
                      </div>
                    </button>
                  ))}

                <div className="flex flex-wrap gap-1 border-b border-border px-2 py-1.5">
                  {(Object.keys(THREAD_FILTER_LABELS) as ThreadFilter[]).map((key) => (
                    <button
                      key={key}
                      onClick={() => setThreadFilter(key)}
                      className={clsx(
                        'rounded-md px-2 py-1 text-[11.5px] font-medium transition-colors',
                        threadFilter === key ? 'bg-accent-subtle text-accent' : 'text-ink-muted hover:bg-surface-hover hover:text-ink-soft',
                      )}
                    >
                      {THREAD_FILTER_LABELS[key]} <span className="tabular-nums opacity-70">{threadFilterCounts[key]}</span>
                    </button>
                  ))}
                </div>

                {filteredGroups.length === 0 ? (
                  <EmptyState
                    icon={Inbox}
                    title={threadFilter === 'all' ? 'Переписки пока нет' : 'Ничего не найдено'}
                    description={threadFilter === 'all' ? 'Отправьте письма поставщикам из заявки.' : 'Попробуйте другой фильтр.'}
                  />
                ) : (
                  filteredGroups.map((g) => {
                    const isOpen = threadFilter !== 'all' || (expanded?.has(g.request_id) ?? false);
                    const unread = g.threads.reduce((s, t) => s + t.unread_count, 0);
                    return (
                      <div key={g.request_id} className="border-b border-border">
                        <button onClick={() => toggleGroup(g.request_id)} className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-surface-hover">
                          <ChevronRight size={13} className={'shrink-0 text-ink-faint transition-transform ' + (isOpen ? 'rotate-90' : '')} />
                          <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-ink">{g.request_name}</span>
                          {unread > 0 && <Badge tone="accent">{unread}</Badge>}
                        </button>
                        {isOpen &&
                          g.threads.map((t) => {
                            const status = threadResponseStatus(t);
                            return (
                              <button
                                key={t.id}
                                onClick={() => selectThread(t.id)}
                                className={
                                  'flex w-full items-center gap-2 border-t border-border/60 py-2 pl-8 pr-3 text-left hover:bg-surface-hover ' +
                                  (activeThread?.id === t.id ? 'border-l-2 border-l-accent bg-accent-subtle/40' : '')
                                }
                              >
                                <Avatar name={t.supplier_name} size="sm" />
                                <div className="min-w-0 flex-1">
                                  <p className={clsx('truncate text-[12px]', t.unread_count > 0 ? 'font-semibold text-ink' : 'font-medium text-ink-soft')}>
                                    {formatCompanyName(t.supplier_name)}
                                  </p>
                                  <p className="truncate text-[11px] text-ink-muted">{formatRelativeTime(t.last_message_at)}</p>
                                </div>
                                {status !== 'none' && (
                                  <span
                                    className={clsx(
                                      'flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-medium',
                                      status === 'answered' ? 'bg-success-subtle text-success' : 'bg-warning-subtle text-warning',
                                    )}
                                    title={responseLabel[status]}
                                  >
                                    {status === 'answered' ? <CheckCheck size={11} /> : <Clock3 size={11} />}
                                    {status === 'answered' ? 'Ответ' : 'Ждём'}
                                  </span>
                                )}
                                {t.unread_count > 0 && (
                                  <span
                                    className="flex h-4 min-w-[16px] shrink-0 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white"
                                    title={`Новых ответов: ${t.unread_count}`}
                                  >
                                    {t.unread_count}
                                  </span>
                                )}
                              </button>
                            );
                          })}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </Panel>

          <Separator className="w-px bg-border transition-colors hover:bg-accent-border" />

          <Panel minSize="35%" className="flex min-w-0 flex-1 flex-col">
            {activeThread ? (
              <>
                <div className="flex items-center gap-3 border-b border-border px-5 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold text-ink">{formatCompanyName(activeThread.supplier_name)}</p>
                    <p className="truncate text-[11.5px] text-ink-muted">{activeThread.request_name}</p>
                  </div>
                  <Badge tone={responseTone[threadResponseStatus(activeThread)]}>{responseLabel[threadResponseStatus(activeThread)]}</Badge>
                  <DeadlineTag deadline={activeDeadline} />
                  <Button variant="secondary" size="sm" icon={<Truck size={13} />} onClick={() => setLogisticsOpen(true)}>
                    Доставка
                  </Button>
                </div>

                {logisticsOpen && (
                  <LogisticsQuoteModal
                    requestId={activeThread.request_id}
                    supplierId={activeThread.supplier_id}
                    supplierName={formatCompanyName(activeThread.supplier_name)}
                    onClose={() => setLogisticsOpen(false)}
                  />
                )}

                <div className="flex-1 overflow-y-auto px-5 py-4">
                  {messagesState.status === 'loading' ? (
                    <LoadingState label="Загружаем сообщения…" />
                  ) : messagesState.status === 'error' ? (
                    <ErrorState message={messagesState.message} onRetry={messagesState.reload} />
                  ) : messagesState.data.length === 0 ? (
                    <EmptyState icon={Inbox} title="В этой переписке пока нет сообщений" />
                  ) : (
                    messagesState.data.map((m) => {
                      const isOutbound = m.direction === 'outbound';
                      const isHighlighted = pendingHighlight?.messageId === m.id;
                      return (
                        <div
                          key={m.id}
                          ref={(el) => {
                            if (el) messageRefs.current.set(m.id, el);
                            else messageRefs.current.delete(m.id);
                          }}
                          className={clsx(
                            'mb-3 min-w-0 rounded-md border-l-2 px-4 py-3',
                            isOutbound ? 'border-l-accent bg-accent-subtle/40' : 'border-l-border-strong bg-surface',
                            isHighlighted && 'ring-1 ring-accent',
                          )}
                        >
                          <div className="mb-1.5 flex items-center gap-3">
                            <span
                              className={clsx(
                                'flex shrink-0 items-center gap-1 text-[11px] font-medium',
                                isOutbound ? 'text-accent' : 'text-ink-muted',
                              )}
                              title={isOutbound ? 'Отправлено нами' : 'Получено от поставщика'}
                            >
                              {isOutbound ? <ArrowUpRight size={12} /> : <ArrowDownLeft size={12} />}
                              {isOutbound ? 'Отправлено' : 'Получено'}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-ink">
                              {messageSenderName(m.direction, formatCompanyName(activeThread.supplier_name), ownerName)}
                            </span>
                            <span className="shrink-0 text-[11px] text-ink-faint">{formatDateTime(m.created_at)}</span>
                          </div>
                          <p className="whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink-soft">
                            {isHighlighted && pendingHighlight ? highlightText(m.body_text ?? '', pendingHighlight.query) : m.body_text}
                          </p>
                          {m.status === 'queued' && <p className="mt-1.5 text-[11px] text-ink-faint">Отправляется…</p>}
                          {m.error && <p className="mt-1.5 text-[11px] text-danger">{m.error}</p>}
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="border-t border-border p-3">
                  <textarea
                    ref={draftRef}
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && draft.trim()) {
                        e.preventDefault();
                        void sendReply();
                      }
                    }}
                    aria-label={`Ответить поставщику ${formatCompanyName(activeThread.supplier_name)}`}
                    placeholder={`Ответить: ${activeThread.supplier_email}`}
                    rows={4}
                    className="max-h-[320px] min-h-[104px] w-full resize-y rounded-md border border-border-strong bg-surface px-3 py-2 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
                  />
                  <div className="mt-2 flex items-center justify-between">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={<Paperclip size={13} />}
                      disabled
                      title="Вложения — скоро"
                    >
                      Прикрепить файл
                    </Button>
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-ink-faint">⌘/Ctrl + Enter — отправить</span>
                      <Button variant="primary" size="sm" icon={<Send size={13} />} onClick={sendReply} disabled={!draft.trim()}>
                        Отправить
                      </Button>
                    </div>
                  </div>
                </div>
              </>
            ) : activeUnmatchedId ? (
              <>
                {conversationState.status === 'loading' ? (
                  <LoadingState label="Загружаем письмо…" />
                ) : conversationState.status === 'error' ? (
                  <ErrorState message={conversationState.message} onRetry={conversationState.reload} />
                ) : conversationState.data ? (
                  <>
                    <div className="border-b border-border px-5 py-2.5">
                      <p className="text-[13px] font-semibold text-ink">{conversationState.data.subject}</p>
                      <p className="text-[11.5px] text-ink-muted">{conversationState.data.from_email}</p>
                    </div>
                    <div className="flex-1 overflow-y-auto px-5 py-4">
                      <div className="min-w-0 rounded-md border-l-2 border-l-border-strong bg-surface px-4 py-3">
                        <p className="whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink-soft">
                          {conversationState.data.body_text || '(нет текстового содержимого — только HTML)'}
                        </p>
                      </div>
                      {conversationState.data.replies.map((m) => {
                        const isOutbound = m.direction === 'outbound';
                        return (
                          <div
                            key={m.id}
                            className={clsx(
                              'mt-3 min-w-0 rounded-md border-l-2 px-4 py-3',
                              isOutbound ? 'border-l-accent bg-accent-subtle/40' : 'border-l-border-strong bg-surface',
                            )}
                          >
                            <div className="mb-1.5 flex items-center gap-3">
                              <span
                                className={clsx('flex shrink-0 items-center gap-1 text-[11px] font-medium', isOutbound ? 'text-accent' : 'text-ink-muted')}
                              >
                                {isOutbound ? <ArrowUpRight size={12} /> : <ArrowDownLeft size={12} />}
                                {isOutbound ? 'Отправлено' : 'Получено'}
                              </span>
                              <span className="shrink-0 text-[11px] text-ink-faint">{formatDateTime(m.created_at)}</span>
                            </div>
                            <p className="whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink-soft">{m.body_text}</p>
                          </div>
                        );
                      })}
                    </div>
                    <div className="border-t border-border p-3">
                      {suggestionsState.status === 'ready' && suggestionsState.data.length > 0 && (
                        <div className="mb-2 flex items-center gap-2 rounded-md bg-info-subtle px-3 py-2 text-[12px] text-info">
                          <Link2 size={13} />
                          Похоже на {formatCompanyName(suggestionsState.data[0].supplier_name)} · «{suggestionsState.data[0].request_name}»
                        </div>
                      )}
                      {linkError && <p className="mb-2 text-[12px] text-danger">{linkError}</p>}

                      <textarea
                        value={unmatchedDraft}
                        onChange={(e) => setUnmatchedDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && unmatchedDraft.trim()) {
                            e.preventDefault();
                            void sendUnmatchedReply();
                          }
                        }}
                        aria-label={`Ответить на письмо от ${conversationState.data.from_email}`}
                        placeholder={`Ответить: ${conversationState.data.from_email}`}
                        rows={3}
                        className="min-h-[88px] w-full resize-y rounded-md border border-border-strong bg-surface px-3 py-2 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
                      />
                      {unmatchedReplyError && <p className="mt-1.5 text-[12px] text-danger">{unmatchedReplyError}</p>}

                      {confirmingIgnore && (
                        <div className="mt-2 flex items-center justify-between gap-3 rounded-md border border-danger-border bg-danger-subtle px-3 py-2">
                          <span className="text-[12.5px] font-medium text-danger">Скрыть это письмо насовсем? Отменить это действие через интерфейс будет нельзя.</span>
                          <div className="flex shrink-0 items-center gap-1.5">
                            <Button
                              variant="secondary"
                              size="sm"
                              className="border-danger-border bg-surface text-danger hover:bg-danger-subtle"
                              disabled={ignoring}
                              onClick={() => void ignoreUnmatched()}
                            >
                              {ignoring ? 'Скрываем…' : 'Да, скрыть'}
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setConfirmingIgnore(false)}>
                              Отмена
                            </Button>
                          </div>
                        </div>
                      )}

                      <div className="mt-2 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {!confirmingIgnore && (
                            <>
                              <Button variant="secondary" size="sm" icon={<Ban size={13} />} onClick={() => setConfirmingIgnore(true)}>
                                Игнорировать
                              </Button>
                              <Button variant="secondary" size="sm" icon={<Link2 size={13} />} onClick={() => setManualLinkOpen(true)}>
                                Связать вручную
                              </Button>
                            </>
                          )}
                          {suggestionsState.status === 'ready' && suggestionsState.data.length > 0 && (
                            <Button variant="primary" size="sm" icon={<Link2 size={13} />} onClick={linkSuggestion} disabled={linking}>
                              {linking ? 'Связываем…' : 'Связать с найденной заявкой'}
                            </Button>
                          )}
                        </div>
                        <Button
                          variant="primary"
                          size="sm"
                          icon={<Send size={13} />}
                          onClick={() => void sendUnmatchedReply()}
                          disabled={sendingUnmatchedReply || !unmatchedDraft.trim()}
                        >
                          {sendingUnmatchedReply ? 'Отправляем…' : 'Ответить'}
                        </Button>
                      </div>
                    </div>
                    {manualLinkOpen && (
                      <ManualLinkModal
                        inboxMessageId={activeUnmatchedId}
                        onClose={() => setManualLinkOpen(false)}
                        onLinked={() => {
                          unmatchedState.reload();
                          threadsState.reload();
                          setSelection(null);
                        }}
                      />
                    )}
                  </>
                ) : null}
              </>
            ) : (
              <EmptyState icon={Inbox} title="Выберите переписку" description="Слева — заявки и письма без привязки." />
            )}
          </Panel>
        </Group>

        {notesOpen && activeThread && (
          <NotesPanel
            requestId={activeThread.request_id}
            supplierId={activeThread.supplier_id}
            onClose={() => setNotesOpen(false)}
            onSaved={() => noteState.reload()}
          />
        )}

        {tasksOpen && activeThread && (
          <TasksPanel requestId={activeThread.request_id} supplierId={activeThread.global_supplier_id} onClose={() => setTasksOpen(false)} />
        )}

        {aiOpen && (activeThread || activeUnmatchedId) && (
          <AiChatPanel
            key={activeThread ? `thread-${activeThread.id}` : `unmatched-${activeUnmatchedId}`}
            storageKey={activeThread ? `thread-${activeThread.id}` : `unmatched-${activeUnmatchedId}`}
            context={buildAiContext(activeThread, messagesState, activeUnmatchedId, conversationState, aiExtraThreadsForContext)}
            siblingThreads={siblingThreads.map((t) => ({ id: t.id, name: formatCompanyName(t.supplier_name) }))}
            selectedSiblingIds={aiExtraThreadIds}
            onToggleSibling={(id) => setAiExtraThreadIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))}
            onClose={() => setAiOpen(false)}
          />
        )}

        <div className="flex w-12 shrink-0 flex-col items-center gap-1 border-l border-border py-3">
          <button
            type="button"
            disabled={!activeThread}
            onClick={() => {
              setNotesOpen((v) => !v);
              setTasksOpen(false);
              setAiOpen(false);
            }}
            title={activeThread ? (hasNote ? 'Заметки — есть заметка' : 'Заметки') : 'Заметки — откройте переписку по заявке'}
            className={clsx(
              'relative flex h-9 w-9 items-center justify-center rounded-md',
              !activeThread
                ? 'cursor-not-allowed text-ink-faint'
                : notesOpen
                  ? 'bg-accent-subtle text-accent'
                  : hasNote
                    ? 'text-warning hover:bg-surface-hover'
                    : 'text-ink-muted hover:bg-surface-hover hover:text-ink',
            )}
          >
            <StickyNote size={16} fill={hasNote && !notesOpen ? 'currentColor' : 'none'} />
            {hasNote && !notesOpen && (
              <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-warning ring-2 ring-surface" />
            )}
          </button>
          <button
            type="button"
            disabled={!activeThread}
            onClick={() => {
              setTasksOpen((v) => !v);
              setNotesOpen(false);
              setAiOpen(false);
            }}
            title={activeThread ? 'Задачи' : 'Задачи — откройте переписку по заявке'}
            className={clsx(
              'flex h-9 w-9 items-center justify-center rounded-md',
              !activeThread
                ? 'cursor-not-allowed text-ink-faint'
                : tasksOpen
                  ? 'bg-accent-subtle text-accent'
                  : 'text-ink-muted hover:bg-surface-hover hover:text-ink',
            )}
          >
            <SquareCheck size={16} />
          </button>
          <button
            type="button"
            disabled={!activeThread && !activeUnmatchedId}
            onClick={() => {
              setAiOpen((v) => !v);
              setNotesOpen(false);
              setTasksOpen(false);
            }}
            title={activeThread || activeUnmatchedId ? 'ИИ-помощник' : 'ИИ-помощник — откройте переписку'}
            className={clsx(
              'flex h-9 w-9 items-center justify-center rounded-md',
              !activeThread && !activeUnmatchedId
                ? 'cursor-not-allowed text-ink-faint'
                : aiOpen
                  ? 'bg-accent-subtle text-accent'
                  : 'text-ink-muted hover:bg-surface-hover hover:text-ink',
            )}
          >
            <Sparkles size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
