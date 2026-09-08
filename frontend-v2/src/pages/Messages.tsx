import {
  Ban,
  ChevronRight,
  Inbox,
  Link2,
  Send,
  Sparkles,
  SquareCheck,
  StickyNote,
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { PageHeader } from '../components/shell/PageHeader';
import { Avatar } from '../components/ui/Avatar';
import { Badge, type Tone } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';
import { threadResponseStatus, messageSenderName, type ResponseStatus } from '../lib/derive';
import { formatDateTime, formatRelativeTime } from '../lib/format';
import type { ThreadSummary } from '../lib/types';
import { useApiData } from '../lib/useApiData';

type Selection = { type: 'thread'; id: number } | { type: 'unmatched'; id: number } | null;

const responseTone: Record<ResponseStatus, Tone> = { none: 'neutral', waiting: 'warning', answered: 'success' };
const responseLabel: Record<ResponseStatus, string> = { none: 'Не отправлено', waiting: 'Ожидаем ответ', answered: 'Есть ответ' };

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

  const [expanded, setExpanded] = useState<Set<number> | null>(null);
  useEffect(() => {
    if (expanded === null && groups.length > 0) {
      setExpanded(new Set(groups.filter((g) => g.threads.some((t) => t.unread_count > 0)).map((g) => g.request_id)));
    }
  }, [groups, expanded]);

  const [selection, setSelection] = useState<Selection>(null);
  const [selectionInitialized, setSelectionInitialized] = useState(false);
  useEffect(() => {
    if (!selectionInitialized && threads.length > 0) {
      const firstUnread = threads.find((t) => t.unread_count > 0) ?? threads[0];
      setSelection({ type: 'thread', id: firstUnread.id });
      setSelectionInitialized(true);
    }
  }, [threads, selectionInitialized]);

  const [draft, setDraft] = useState('');

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
  const suggestionsState = useApiData(
    () => (activeUnmatchedId ? api.inboxSuggestions(activeUnmatchedId).then((r) => r.items) : Promise.resolve([])),
    [activeUnmatchedId],
  );

  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState<string | null>(null);

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

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader title="Сообщения" description="Заявка → поставщик → переписка · реальные данные" />
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
                  onClick={() => unmatched[0] && setSelection({ type: 'unmatched', id: unmatched[0].id })}
                  className="flex w-full items-center gap-2.5 border-b border-border px-3 py-2.5 text-left hover:bg-surface-hover"
                >
                  <Inbox size={14} className="text-ink-muted" />
                  <span className="flex-1 text-[12.5px] font-medium text-ink">Новые письма без заявки</span>
                  {unmatched.length > 0 && <Badge tone="accent">{unmatched.length}</Badge>}
                </button>
                {selection?.type === 'unmatched' &&
                  unmatched.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setSelection({ type: 'unmatched', id: m.id })}
                      className={
                        'flex w-full items-start gap-2 border-b border-border py-2 pl-8 pr-3 text-left hover:bg-surface-hover ' +
                        (activeUnmatchedId === m.id ? 'border-l-2 border-l-accent bg-accent-subtle/40' : '')
                      }
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12px] font-medium text-ink">{m.subject}</p>
                        <p className="truncate text-[11px] text-ink-muted">{m.from_email}</p>
                      </div>
                      {m.unread && <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />}
                    </button>
                  ))}

                {groups.length === 0 ? (
                  <EmptyState icon={Inbox} title="Переписки пока нет" description="Отправьте письма поставщикам из заявки." />
                ) : (
                  groups.map((g) => {
                    const isOpen = expanded?.has(g.request_id) ?? false;
                    const unread = g.threads.reduce((s, t) => s + t.unread_count, 0);
                    return (
                      <div key={g.request_id} className="border-b border-border">
                        <button onClick={() => toggleGroup(g.request_id)} className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-surface-hover">
                          <ChevronRight size={13} className={'shrink-0 text-ink-faint transition-transform ' + (isOpen ? 'rotate-90' : '')} />
                          <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-ink">{g.request_name}</span>
                          {unread > 0 && <Badge tone="accent">{unread}</Badge>}
                        </button>
                        {isOpen &&
                          g.threads.map((t) => (
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
                                <p className="truncate text-[12px] font-medium text-ink">{t.supplier_name}</p>
                                <p className="truncate text-[11px] text-ink-muted">{formatRelativeTime(t.last_message_at)}</p>
                              </div>
                              {t.unread_count > 0 && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />}
                            </button>
                          ))}
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
                    <p className="truncate text-[13px] font-semibold text-ink">{activeThread.supplier_name}</p>
                    <p className="truncate text-[11.5px] text-ink-muted">{activeThread.request_name}</p>
                  </div>
                  <Badge tone={responseTone[threadResponseStatus(activeThread)]}>{responseLabel[threadResponseStatus(activeThread)]}</Badge>
                  <DeadlineTag deadline={activeDeadline} />
                </div>

                <div className="flex-1 overflow-y-auto px-5 py-4">
                  {messagesState.status === 'loading' ? (
                    <LoadingState label="Загружаем сообщения…" />
                  ) : messagesState.status === 'error' ? (
                    <ErrorState message={messagesState.message} onRetry={messagesState.reload} />
                  ) : messagesState.data.length === 0 ? (
                    <EmptyState icon={Inbox} title="В этой переписке пока нет сообщений" />
                  ) : (
                    messagesState.data.map((m) => (
                      <div
                        key={m.id}
                        className={'mb-3 max-w-[72ch] rounded-md border-l-2 bg-surface px-4 py-3 ' + (m.direction === 'outbound' ? 'border-l-accent' : 'border-l-border-strong')}
                      >
                        <div className="mb-1.5 flex items-center justify-between gap-3">
                          <span className="truncate text-[12.5px] font-semibold text-ink">
                            {messageSenderName(m.direction, activeThread.supplier_name, ownerName)}
                          </span>
                          <span className="shrink-0 text-[11px] text-ink-faint">{formatDateTime(m.created_at)}</span>
                        </div>
                        <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink-soft">{m.body_text}</p>
                        {m.status === 'queued' && <p className="mt-1.5 text-[11px] text-ink-faint">Отправляется…</p>}
                        {m.error && <p className="mt-1.5 text-[11px] text-danger">{m.error}</p>}
                      </div>
                    ))
                  )}
                </div>

                <div className="border-t border-border p-3">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    aria-label={`Ответить поставщику ${activeThread.supplier_name}`}
                    placeholder={`Ответить: ${activeThread.supplier_email}`}
                    rows={3}
                    className="w-full resize-none rounded-md border border-border-strong bg-surface px-3 py-2 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
                  />
                  <div className="mt-2 flex items-center justify-end">
                    <Button variant="primary" size="sm" icon={<Send size={13} />} onClick={sendReply} disabled={!draft.trim()}>
                      Отправить
                    </Button>
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
                      <div className="max-w-[72ch] rounded-md border-l-2 border-l-border-strong bg-surface px-4 py-3">
                        <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink-soft">
                          {conversationState.data.body_text || '(нет текстового содержимого — только HTML)'}
                        </p>
                      </div>
                    </div>
                    <div className="border-t border-border p-3">
                      {suggestionsState.status === 'ready' && suggestionsState.data.length > 0 && (
                        <div className="mb-2 flex items-center gap-2 rounded-md bg-info-subtle px-3 py-2 text-[12px] text-info">
                          <Link2 size={13} />
                          Похоже на {suggestionsState.data[0].supplier_name} · «{suggestionsState.data[0].request_name}»
                        </div>
                      )}
                      {linkError && <p className="mb-2 text-[12px] text-danger">{linkError}</p>}
                      <div className="flex items-center justify-end gap-2">
                        <Button variant="secondary" size="sm" icon={<Ban size={13} />} disabled title="На бэкенде пока нет метода «игнорировать» непривязанное письмо">
                          Игнорировать
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          icon={<Link2 size={13} />}
                          onClick={linkSuggestion}
                          disabled={linking || suggestionsState.status !== 'ready' || suggestionsState.data.length === 0}
                        >
                          {linking ? 'Связываем…' : suggestionsState.status === 'ready' && suggestionsState.data.length > 0 ? 'Связать с заявкой' : 'Нет подходящей заявки'}
                        </Button>
                      </div>
                    </div>
                  </>
                ) : null}
              </>
            ) : (
              <EmptyState icon={Inbox} title="Выберите переписку" description="Слева — заявки и письма без привязки." />
            )}
          </Panel>
        </Group>

        <div className="flex w-12 shrink-0 flex-col items-center gap-1 border-l border-border py-3">
          {[
            { icon: StickyNote, label: 'Заметки' },
            { icon: SquareCheck, label: 'Задачи' },
            { icon: Sparkles, label: 'AI' },
          ].map(({ icon: Icon, label }) => (
            <button key={label} disabled title={`${label} — скоро`} className="flex h-9 w-9 cursor-not-allowed items-center justify-center rounded-md text-ink-faint">
              <Icon size={16} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
