import { useEffect, useMemo, useState, type DragEvent } from 'react';
import { ChevronDown, ChevronRight, Clock3, Mail } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { cn, displayCorrespondenceSupplierName, formatRelativeDate, pluralize } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';
import { getThreadDisplayStatus, isAwaitingResponse, isPrimaryCorrespondence, needsThreadAttention } from '@/components/mail/threadStatus';
import { ThreadMetadataControls } from '@/components/mail/ThreadMetadataControls';
import { UnmatchedPreview } from '@/components/mail/UnmatchedPreview';
import { Button } from '@/components/ui/Button';
import { Count, StatusBadge } from '@/components/ui/StatusBadge';

/** Переписка сгруппирована по заявке, а не сплошным списком.
 *
 *  Закупщик работает заявкой: «что мне ответили по насосам» — вопрос про
 *  заявку, а не про отдельного поставщика. Плоский список заставлял держать
 *  в голове, какая строка к какой закупке относится, и при десятке заявок
 *  читался как общий почтовый ящик, ради ухода от которого продукт и делается.
 *
 *  Заявки отсортированы по свежести последнего письма, внутри — поставщики
 *  так же. Группа с непрочитанными ответами раскрыта, остальные свёрнуты:
 *  список остаётся коротким, а то, что требует внимания, видно сразу.
 *  Письма, которые ещё только отправляются или требуют проверки доставки,
 *  находятся в отдельной вкладке очереди и не смешиваются с историей. */
interface RequestGroup {
  requestId: number;
  requestName: string;
  threads: ThreadSummary[];
  lastMessageAt: string | null;
  repliesCount: number;
  unreadCount: number;
}

function groupByRequest(threads: ThreadSummary[]): RequestGroup[] {
  const groups = new Map<number, RequestGroup>();
  for (const thread of threads) {
    let group = groups.get(thread.request_id);
    if (!group) {
      group = {
        requestId: thread.request_id,
        requestName: thread.request_name,
        threads: [],
        lastMessageAt: null,
        repliesCount: 0,
        unreadCount: 0,
      };
      groups.set(thread.request_id, group);
    }
    group.threads.push(thread);
    group.repliesCount += thread.replies_count;
    group.unreadCount += thread.unread_count;
    if (!group.lastMessageAt || (thread.last_message_at ?? '') > group.lastMessageAt) {
      group.lastMessageAt = thread.last_message_at;
    }
  }
  const list = [...groups.values()];
  for (const group of list) {
    group.threads.sort((a, b) => (b.last_message_at ?? '').localeCompare(a.last_message_at ?? ''));
  }
  list.sort((a, b) => (b.lastMessageAt ?? '').localeCompare(a.lastMessageAt ?? ''));
  return list;
}

interface ThreadListProps {
  selectedThreadKey: string | null;
  onSelectThread: (thread: ThreadSummary) => void;
  refreshKey: number;
  searchInput: string;
  onOpenUnmatched: (messageId?: number) => void;
  onDropUnmatched: (messageId: number, requestId: number) => Promise<void>;
  onMetadataChange: (thread: ThreadSummary, patch: { important?: boolean; priority?: 1 | 2 | 3 | null }) => Promise<void>;
}

type ThreadFilter = 'primary' | 'awaiting-response';

export function ThreadList({ selectedThreadKey, onSelectThread, refreshKey, searchInput, onOpenUnmatched, onDropUnmatched, onMetadataChange }: ThreadListProps) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const [filter, setFilter] = useState<ThreadFilter>('primary');
  const [draggedInboxId, setDraggedInboxId] = useState<number | null>(null);
  const [dropTargetRequestId, setDropTargetRequestId] = useState<number | null>(null);
  const [dropBusy, setDropBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api
      .listThreads()
      .then((res) => {
        if (!cancelled) setThreads(res.items);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, retryToken]);

  const searchedThreads = useMemo(() => {
    if (!searchInput.trim()) return threads;
    const q = searchInput.trim().toLowerCase();
    return threads.filter(
      (t) =>
        t.subject.toLowerCase().includes(q) ||
        t.request_name.toLowerCase().includes(q) ||
        t.supplier_name.toLowerCase().includes(q) ||
        t.supplier_email.toLowerCase().includes(q) ||
        t.supplier_host.toLowerCase().includes(q)
    );
  }, [threads, searchInput]);

  const primaryThreads = useMemo(
    () => searchedThreads.filter(isPrimaryCorrespondence),
    [searchedThreads],
  );

  const visibleThreads = useMemo(
    () => filter === 'awaiting-response' ? primaryThreads.filter(isAwaitingResponse) : primaryThreads,
    [filter, primaryThreads],
  );

  const groups = useMemo(() => groupByRequest(visibleThreads), [visibleThreads]);
  const defaultCollapsed = useMemo(
    () => new Set(groups
      .filter((group) => !group.threads.some(needsThreadAttention))
      .map((group) => group.requestId)),
    [groups],
  );

  // Свёрнутость хранится как множество ЗАКРЫТЫХ заявок, а не открытых: тогда
  // новая заявка, появившаяся после синхронизации, по умолчанию раскрыта и не
  // прячет свежий ответ.
  const [collapsed, setCollapsed] = useState<Set<number> | null>(null);
  const toggle = (requestId: number) =>
    setCollapsed((prev) => {
      const next = new Set(prev ?? defaultCollapsed);
      if (next.has(requestId)) next.delete(requestId);
      else next.add(requestId);
      return next;
    });

  const awaitingCount = primaryThreads.filter(isAwaitingResponse).length;
  // При поиске или фильтрации показываем всё раскрытым: иначе совпадение
  // может оказаться внутри свёрнутой группы и будет выглядеть как «ничего
  // не найдено».
  const searching = Boolean(searchInput.trim());
  const narrowing = searching || filter !== 'primary';

  const handleDrop = async (event: DragEvent<HTMLDivElement>, requestId: number) => {
    event.preventDefault();
    const rawId = event.dataTransfer.getData('application/x-supplydesk-inbox-id');
    const messageId = Number(rawId);
    setDropTargetRequestId(null);
    setDraggedInboxId(null);
    if (!messageId || dropBusy) return;
    setDropBusy(true);
    try {
      await onDropUnmatched(messageId, requestId);
    } finally {
      setDropBusy(false);
    }
  };

  return (
    <div className={cn(
      'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[400px] 2xl:w-[420px] xl:flex',
      selectedThreadKey ? 'hidden' : 'flex',
    )}>
      <div className="shrink-0 border-b border-ink-100 bg-ink-50/70 px-4 pt-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-ink-900">Переписки</h2>
          <Count value={primaryThreads.length} label="Количество переписок" />
        </div>
        <div className="mt-3 flex items-center gap-4 border-b border-ink-200" role="group" aria-label="Фильтр по статусу">
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={filter === 'primary'}
            onClick={() => setFilter('primary')}
            className={cn(
              'relative min-h-9 rounded-none px-0 text-xs after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-transparent',
              filter === 'primary' ? 'text-ink-900 after:bg-accent-600' : 'text-ink-500 hover:bg-transparent hover:text-ink-800',
            )}
          >
            Отправленные и ответы <Count value={primaryThreads.length} />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={filter === 'awaiting-response'}
            onClick={() => setFilter('awaiting-response')}
            className={cn(
              'relative min-h-9 rounded-none px-0 text-xs after:absolute after:inset-x-0 after:-bottom-px after:h-0.5 after:bg-transparent',
              filter === 'awaiting-response' ? 'text-ink-900 after:bg-accent-600' : 'text-ink-500 hover:bg-transparent hover:text-ink-800',
            )}
          >
            <Clock3 size={13} aria-hidden="true" />Ожидает ответа <Count value={awaitingCount} />
          </Button>
        </div>
      </div>

      <UnmatchedPreview
        refreshKey={refreshKey}
        onShowAll={() => onOpenUnmatched()}
        onOpenMessage={(messageId) => onOpenUnmatched(messageId)}
        onDragStart={setDraggedInboxId}
        onDragEnd={() => { setDraggedInboxId(null); setDropTargetRequestId(null); }}
      />

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="p-3 space-y-2">
                <div className="h-3 w-1/2 bg-ink-100 rounded animate-pulse" />
                <div className="h-3 w-3/4 bg-ink-100 rounded animate-pulse" />
                <div className="h-3 w-2/3 bg-ink-100 rounded animate-pulse" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <Mail size={30} className="mb-3 text-ink-300" />
            <p className="text-sm text-ink-500">Не удалось загрузить письма</p>
            <button type="button" onClick={() => setRetryToken((value) => value + 1)} className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-accent-700 hover:bg-accent-50">
              Повторить
            </button>
          </div>
        ) : visibleThreads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <Mail size={32} className="text-ink-300 mb-3" />
            <p className="text-sm text-ink-500">
              {filter === 'awaiting-response'
                ? 'Нет писем, ожидающих ответа'
                : searchInput.trim()
                  ? 'По вашему поиску ничего не найдено'
                  : 'Нет отправленных писем или ответов'}
            </p>
          </div>
        ) : (
          <div className="py-1">
            {groups.map((group) => {
              const isCollapsed = !narrowing && (collapsed ?? defaultCollapsed).has(group.requestId);
              return (
                <div key={group.requestId} className="mb-0.5">
                  <div
                    onDragOver={(event) => {
                      if (draggedInboxId != null) {
                        event.preventDefault();
                        event.dataTransfer.dropEffect = 'move';
                        setDropTargetRequestId(group.requestId);
                      }
                    }}
                    onDragLeave={() => setDropTargetRequestId((current) => current === group.requestId ? null : current)}
                    onDrop={(event) => void handleDrop(event, group.requestId)}
                    className={cn(
                      'sticky top-0 z-10 flex items-center gap-1 border-y border-transparent bg-white/95 px-2 py-1.5 backdrop-blur-sm transition-colors',
                      draggedInboxId != null && dropTargetRequestId === group.requestId && 'border-accent-300 bg-accent-50/95 ring-2 ring-inset ring-accent-300',
                    )}
                  >
                    <button
                      onClick={() => toggle(group.requestId)}
                      aria-expanded={!isCollapsed}
                      className="flex min-h-10 min-w-0 flex-1 items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
                    >
                      {isCollapsed
                        ? <ChevronRight size={14} className="shrink-0 text-ink-400" />
                        : <ChevronDown size={14} className="shrink-0 text-ink-400" />}
                      <span className="truncate text-sm font-semibold text-ink-800" title={group.requestName}>
                        {group.requestName}
                      </span>
                      <span className="shrink-0 text-xs text-ink-600">
                        {group.threads.length}
                      </span>
                      {group.unreadCount > 0 && (
                        <span
                          title={`${group.unreadCount} ${pluralize(group.unreadCount, 'непрочитанный ответ', 'непрочитанных ответа', 'непрочитанных ответов')}`}
                          className="shrink-0 rounded-full bg-emerald-50 px-1.5 py-px text-2xs font-semibold text-emerald-700 ring-1 ring-emerald-200/70"
                        >
                          {group.unreadCount}
                        </span>
                      )}
                    </button>
                    <Link
                      to={`/requests/${group.requestId}`}
                      title="Открыть заявку"
                      className="inline-flex min-h-10 shrink-0 items-center rounded px-1.5 py-0.5 text-xs font-medium text-accent-600 hover:bg-accent-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
                    >
                      Заявка
                    </Link>
                    {draggedInboxId != null && dropTargetRequestId === group.requestId && <span className="hidden shrink-0 text-2xs font-semibold text-accent-700 sm:inline">Отпустите для привязки</span>}
                  </div>

                  {!isCollapsed && group.threads.map((thread) => {
                    const key = thread.manual_inbox_id != null
                      ? `manual:${thread.manual_inbox_id}`
                      : `${thread.request_id}:${thread.supplier_id}`;
                    const isSelected = selectedThreadKey === key;
                    const hasReplies = thread.replies_count > 0;
                    // Подсвечиваем непрочитанное, а не «когда-либо отвечал»:
                    // иначе отметка не гаснет после открытия письма.
                    const isUnread = thread.unread_count > 0;
                    const status = getThreadDisplayStatus(thread);
                    const supplierLabel = displayCorrespondenceSupplierName(thread.supplier_name) || 'Поставщик не определён';
                    return (
                      <div key={key} className={cn('flex items-start', isSelected ? 'bg-accent-50/50' : 'hover:bg-ink-50')}>
                        {thread.manual_inbox_id == null && (
                          <ThreadMetadataControls
                            important={thread.is_important}
                            priority={thread.priority}
                            onChange={(patch) => onMetadataChange(thread, patch)}
                          />
                        )}
                        <button
                          type="button"
                          onClick={() => onSelectThread(thread)}
                          aria-label={`${supplierLabel}: ${thread.subject}. ${status.label}`}
                          className={cn(
                            'min-w-0 flex-1 border-l-2 py-2.5 pl-7 pr-1 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-400',
                            isSelected ? 'border-accent-500' : 'border-transparent'
                          )}
                        >
                          <div className="flex items-start gap-2">
                          <span
                            title={isUnread ? 'Непрочитанный ответ поставщика' : undefined}
                            className={cn('mt-1.5 block h-2 w-2 shrink-0 rounded-full', isUnread ? 'bg-emerald-500' : 'bg-transparent')}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="mb-0.5 flex items-center justify-between gap-2">
                              <span className={cn('min-w-0 truncate text-sm', isUnread ? 'font-semibold text-ink-800' : 'font-medium text-ink-700')} title={thread.supplier_name || undefined}>
                                {supplierLabel}
                              </span>
                              <span className="shrink-0 text-xs text-ink-600">{formatRelativeDate(thread.last_message_at)}</span>
                            </div>
                            <p className="truncate text-xs text-ink-500">
                              {thread.subject}
                              {thread.manual_inbox_id != null && <span className="ml-1.5 text-accent-600">· вручную</span>}
                            </p>
                            <div className="mt-1.5 flex min-w-0 items-center gap-2">
                              {!isAwaitingResponse(thread) && (
                                <StatusBadge label={status.label} tone={status.tone} title={status.title} />
                              )}
                              <span className="min-w-0 flex-1 truncate text-xs text-ink-600">
                                {thread.messages_count} {pluralize(thread.messages_count, 'письмо', 'письма', 'писем')}
                                {hasReplies && <> · {thread.replies_count} {pluralize(thread.replies_count, 'ответ', 'ответа', 'ответов')}</>}
                              </span>
                            </div>
                          </div>
                          </div>
                        </button>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
