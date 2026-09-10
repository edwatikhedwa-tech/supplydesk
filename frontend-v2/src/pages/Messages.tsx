import clsx from 'clsx';
import {
  ArrowDownLeft,
  ArrowLeft,
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
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { useSearchParams } from 'react-router-dom';
import { AiChatPanel } from '../components/AiChatPanel';
import { LogisticsQuoteModal } from '../components/LogisticsQuoteModal';
import { ManualLinkModal } from '../components/ManualLinkModal';
import { SupplierCardPanel } from '../components/SupplierCardPanel';
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
import { useIsNarrowViewport } from '../lib/useIsNarrowViewport';

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
  const isNarrow = useIsNarrowViewport();
  // Mobile only: which single pane is visible. Desktop always shows both
  // side by side (this state is simply unused there).
  const [mobileView, setMobileView] = useState<'list' | 'conversation'>('list');

  const threadsState = useApiData(() => api.listThreads().then((r) => r.items), []);
  const requestsState = useApiData(() => api.listRequests().then((r) => r.items), []);
  // Full list, not just the top-5-most-recent preview -- a reply that never
  // matched a supplier/request (wrong reply-to address is the common cause)
  // previously had no way to surface once it aged out of "this week" or got
  // read, since that was the only view of unmatched mail. See
  // TASK-MAIL-SYNC-DATA-LOSS-20260910.
  const unmatchedState = useApiData(() => api.listInboxUnmatchedAll().then((r) => r.items), []);
  const [showAllUnmatched, setShowAllUnmatched] = useState(false);

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
    // A deep link into a specific conversation should open straight to it on
    // mobile too, not land on the list needing one more tap.
    if (requestedThreadId && isNarrow) setMobileView('conversation');
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
  // can pull in for cross-supplier comparison ("who quoted lowest?"). Scoped
  // to `threadResponseStatus === 'answered'` (replies_count > 0) -- the same
  // "Есть ответ" badge shown in the thread list -- not merely "we sent them
  // something". A request can have 100+ suppliers we've emailed and only a
  // handful who actually replied; only the ones with a real reply belong in
  // an AI comparison ("who quoted lowest?" needs an actual quote to compare).
  // See docs/ui/MESSAGES_SCREEN_SPEC.md ("AI-context invariant").
  const siblingThreads = activeThread
    ? threads.filter((t) => t.request_id === activeThread.request_id && t.id !== activeThread.id && threadResponseStatus(t) === 'answered')
    : [];

  // Scoped to the *request*, not the thread: the extra-suppliers selection is
  // a cross-supplier comparison for one campaign. Clearing it on every thread
  // switch (the previous behavior) wiped it the moment the user opened one of
  // the very suppliers they had just checked, to read that reply -- a normal
  // step in building a multi-supplier comparison, not a request to start
  // over. Switching to a thread on a *different* request is a genuinely new
  // context and still clears it.
  useEffect(() => {
    setAiExtraThreadIds([]);
    setAiExtraMessages({});
  }, [activeThread?.request_id]);

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
    // A selection made while a different sibling was primary can now point at
    // the current activeThread itself (the reset above only fires on a
    // request change, not a thread change -- deliberately, see that effect's
    // comment). Exclude it here so its own reply is never sent to the AI
    // both as the primary conversation and again as an "extra" one.
    .filter((id) => id !== activeThread?.id)
    .map((id) => {
      const thread = threads.find((t) => t.id === id);
      return thread ? { thread, messages: aiExtraMessages[id] ?? [] } : null;
    })
    .filter((x): x is { thread: ThreadSummary; messages: MailMessage[] } => x !== null)
    // Last-line-of-defense re-check at the exact point the payload is built,
    // not just at the UI entry points (checkbox visibility / "select all") --
    // the actual string sent to the AI must never carry a supplier without a
    // real reply, regardless of how aiExtraThreadIds got populated.
    .filter((x) => threadResponseStatus(x.thread) === 'answered');

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
    if (isNarrow) setMobileView('conversation');
  }

  function selectUnmatched(id: number) {
    setSelection({ type: 'unmatched', id });
    if (isNarrow) setMobileView('conversation');
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
  // Everything the weekly widget's unread+7-day filter leaves out -- older
  // or already-read unmatched mail that was otherwise permanently invisible.
  const olderUnmatched = useMemo(() => {
    const weeklyIds = new Set(weeklyUnmatched.map((m) => m.id));
    return unmatched.filter((m) => !weeklyIds.has(m.id));
  }, [unmatched, weeklyUnmatched]);

  const threadListPane: ReactNode = (
    <>
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
            onClick={() => weeklyUnmatched[0] && selectUnmatched(weeklyUnmatched[0].id)}
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
                onClick={() => selectUnmatched(m.id)}
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

          {olderUnmatched.length > 0 && (
            <>
              <button
                onClick={() => setShowAllUnmatched((v) => !v)}
                className="flex w-full items-center gap-2.5 border-b border-border px-3 py-2 text-left hover:bg-surface-hover"
              >
                <span className="flex-1 text-[11.5px] font-medium text-ink-muted">
                  {showAllUnmatched ? 'Скрыть остальные без заявки' : 'Показать остальные без заявки'}
                </span>
                <Badge tone="neutral">{olderUnmatched.length}</Badge>
              </button>
              {showAllUnmatched &&
                olderUnmatched.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => selectUnmatched(m.id)}
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
            </>
          )}

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
                      const inAiContext = aiExtraThreadIds.includes(t.id);
                      // Only offer AI-context selection for the thread's siblings on the
                      // same request while the panel is open -- not the active thread
                      // itself (it's already the primary context, not an "extra"), and
                      // only for "Есть ответ" (see siblingThreads above -- kept in sync).
                      const showAiCheckbox =
                        aiOpen && activeThread && t.request_id === activeThread.request_id && t.id !== activeThread.id && status === 'answered';
                      return (
                        <div
                          key={t.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => selectThread(t.id)}
                          onKeyDown={(e) => e.key === 'Enter' && selectThread(t.id)}
                          className={clsx(
                            'flex w-full cursor-pointer items-center gap-2 border-t border-border/60 py-2 pl-8 pr-3 text-left hover:bg-surface-hover',
                            activeThread?.id === t.id
                              ? 'border-l-2 border-l-accent bg-accent-subtle/40'
                              : inAiContext
                                ? 'border-l-2 border-l-accent/50 bg-accent-subtle/15'
                                : '',
                          )}
                        >
                          {showAiCheckbox && (
                            <input
                              type="checkbox"
                              checked={inAiContext}
                              onClick={(e) => e.stopPropagation()}
                              onChange={() => setAiExtraThreadIds((prev) => (prev.includes(t.id) ? prev.filter((x) => x !== t.id) : [...prev, t.id]))}
                              aria-label={`Добавить ${formatCompanyName(t.supplier_name)} в контекст ИИ`}
                              title="Добавить в контекст ИИ-помощника"
                              className="h-3.5 w-3.5 shrink-0 rounded border-border-strong accent-accent"
                            />
                          )}
                          <Avatar name={t.supplier_name} size="sm" />
                          <div className="min-w-0 flex-1">
                            <p className={clsx('flex items-center gap-1 truncate text-[12px]', t.unread_count > 0 ? 'font-semibold text-ink' : 'font-medium text-ink-soft')}>
                              {inAiContext && <Sparkles size={10} className="shrink-0 text-accent" />}
                              <span className="truncate">{formatCompanyName(t.supplier_name)}</span>
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
                        </div>
                      );
                    })}
                </div>
              );
            })
          )}
        </div>
      )}
    </>
  );

  const backToListButton = isNarrow && (
    <button
      type="button"
      onClick={() => setMobileView('list')}
      className="flex items-center gap-1.5 border-b border-border px-4 py-2.5 text-[12.5px] font-medium text-ink-muted hover:bg-surface-hover hover:text-ink"
    >
      <ArrowLeft size={14} />
      Ко всем перепискам
    </button>
  );

  const conversationPane: ReactNode = activeThread ? (
    <>
      {backToListButton}
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-2.5 sm:px-5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-ink">{formatCompanyName(activeThread.supplier_name)}</p>
          <p className="truncate text-[11.5px] text-ink-muted">{activeThread.request_name}</p>
        </div>
        <Badge tone={responseTone[threadResponseStatus(activeThread)]}>{responseLabel[threadResponseStatus(activeThread)]}</Badge>
        <DeadlineTag deadline={activeDeadline} />
        <Button variant="secondary" size="sm" icon={<Truck size={13} />} onClick={() => setLogisticsOpen(true)}>
          Доставка
        </Button>
        {isNarrow && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => {
                setNotesOpen((v) => !v);
                setTasksOpen(false);
                setAiOpen(false);
              }}
              title="Заметки"
              className={clsx('relative flex h-8 w-8 items-center justify-center rounded-md', notesOpen ? 'bg-accent-subtle text-accent' : hasNote ? 'text-warning' : 'text-ink-muted hover:bg-surface-hover')}
            >
              <StickyNote size={15} fill={hasNote && !notesOpen ? 'currentColor' : 'none'} />
            </button>
            <button
              type="button"
              onClick={() => {
                setTasksOpen((v) => !v);
                setNotesOpen(false);
                setAiOpen(false);
              }}
              title="Задачи"
              className={clsx('flex h-8 w-8 items-center justify-center rounded-md', tasksOpen ? 'bg-accent-subtle text-accent' : 'text-ink-muted hover:bg-surface-hover')}
            >
              <SquareCheck size={15} />
            </button>
            <button
              type="button"
              onClick={() => {
                setAiOpen((v) => !v);
                setNotesOpen(false);
                setTasksOpen(false);
              }}
              title="ИИ-помощник"
              className={clsx('flex h-8 w-8 items-center justify-center rounded-md', aiOpen ? 'bg-accent-subtle text-accent' : 'text-ink-muted hover:bg-surface-hover')}
            >
              <Sparkles size={15} />
            </button>
          </div>
        )}
      </div>

      {logisticsOpen && (
        <LogisticsQuoteModal
          requestId={activeThread.request_id}
          supplierId={activeThread.supplier_id}
          supplierName={formatCompanyName(activeThread.supplier_name)}
          onClose={() => setLogisticsOpen(false)}
        />
      )}

      <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-5">
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
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
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
            <span className="hidden text-[11px] text-ink-faint sm:inline">⌘/Ctrl + Enter — отправить</span>
            <Button variant="primary" size="sm" icon={<Send size={13} />} onClick={sendReply} disabled={!draft.trim()}>
              Отправить
            </Button>
          </div>
        </div>
      </div>
    </>
  ) : activeUnmatchedId ? (
    <>
      {backToListButton}
      {conversationState.status === 'loading' ? (
        <LoadingState label="Загружаем письмо…" />
      ) : conversationState.status === 'error' ? (
        <ErrorState message={conversationState.message} onRetry={conversationState.reload} />
      ) : conversationState.data ? (
        <>
          <div className="border-b border-border px-4 py-2.5 sm:px-5">
            <p className="text-[13px] font-semibold text-ink">{conversationState.data.subject}</p>
            <p className="text-[11.5px] text-ink-muted">{conversationState.data.from_email}</p>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-5">
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
              <div className="mt-2 flex flex-wrap items-center justify-between gap-3 rounded-md border border-danger-border bg-danger-subtle px-3 py-2">
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

            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
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
  );

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader title="Сообщения" />
      <div className="flex min-h-0 flex-1">
        {isNarrow ? (
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">
            {mobileView === 'list' ? threadListPane : conversationPane}
          </div>
        ) : (
          <Group orientation="horizontal" className="flex flex-1">
            <Panel defaultSize="30%" minSize="22%" maxSize="42%" className="flex min-w-0 flex-col border-r border-border">
              {threadListPane}
            </Panel>
            <Separator className="w-px bg-border transition-colors hover:bg-accent-border" />
            <Panel minSize="35%" className="flex min-w-0 flex-1 flex-col">
              {conversationPane}
            </Panel>
          </Group>
        )}

        {/* On mobile these render as full-screen overlays (the panels' own
            root is w-full there); on sm+ the wrapper becomes `contents` --
            an invisible box, so the panel is a normal flex sibling exactly
            as before. */}
        {notesOpen && activeThread && (
          <div className={clsx(isNarrow && 'fixed inset-0 z-40', 'sm:contents')}>
            <SupplierCardPanel
              requestId={activeThread.request_id}
              supplierId={activeThread.supplier_id}
              globalSupplierId={activeThread.global_supplier_id}
              onClose={() => setNotesOpen(false)}
              onNoteSaved={() => noteState.reload()}
            />
          </div>
        )}

        {tasksOpen && activeThread && (
          <div className={clsx(isNarrow && 'fixed inset-0 z-40', 'sm:contents')}>
            <TasksPanel requestId={activeThread.request_id} supplierId={activeThread.global_supplier_id} onClose={() => setTasksOpen(false)} />
          </div>
        )}

        {aiOpen && (activeThread || activeUnmatchedId) && (
          <div className={clsx(isNarrow && 'fixed inset-0 z-40', 'sm:contents')}>
            <AiChatPanel
              key={activeThread ? `thread-${activeThread.id}` : `unmatched-${activeUnmatchedId}`}
              storageKey={activeThread ? `thread-${activeThread.id}` : `unmatched-${activeUnmatchedId}`}
              context={buildAiContext(activeThread, messagesState, activeUnmatchedId, conversationState, aiExtraThreadsForContext)}
              siblingThreads={siblingThreads.map((t) => ({ id: t.id, name: formatCompanyName(t.supplier_name), globalSupplierId: t.global_supplier_id }))}
              selectedSiblingIds={aiExtraThreadIds}
              onToggleSibling={(id) => setAiExtraThreadIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))}
              onSelectAllSiblings={() => setAiExtraThreadIds(siblingThreads.map((t) => t.id))}
              onClearAllSiblings={() => setAiExtraThreadIds([])}
              onClose={() => setAiOpen(false)}
            />
          </div>
        )}

        {/* The vertical icon rail only makes sense with room to spare -- on
            mobile the same three actions live in the conversation header
            instead (see conversationPane), so this whole column is skipped
            there rather than eating ~48px next to an already-narrow pane. */}
        {!isNarrow && (
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
        )}
      </div>
    </div>
  );
}
