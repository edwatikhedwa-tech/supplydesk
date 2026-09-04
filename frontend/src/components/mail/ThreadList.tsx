import { useEffect, useMemo, useState, type DragEvent } from 'react';
import { ChevronDown, ChevronRight, Clock3, Mail, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { cn, displayCorrespondenceSupplierName, formatRelativeDate } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';
import { getThreadDisplayStatus, isAwaitingResponse, isPrimaryCorrespondence, needsThreadAttention } from '@/components/mail/threadStatus';
import { UnmatchedPreview } from '@/components/mail/UnmatchedPreview';
import { Button } from '@/components/ui/Button';
import { Count } from '@/components/ui/StatusBadge';
import { TextField } from '@/components/ui/TextField';

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
  onSearchChange: (value: string) => void;
  onOpenUnmatched: (messageId?: number) => void;
  onDropUnmatched: (messageId: number, requestId: number) => Promise<void>;
}

type ThreadFilter = 'primary' | 'awaiting-response';

export function ThreadList({ selectedThreadKey, onSelectThread, refreshKey, searchInput, onSearchChange, onOpenUnmatched, onDropUnmatched }: ThreadListProps) {
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
      'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[360px] 2xl:w-[380px] xl:flex',
      selectedThreadKey ? 'hidden' : 'flex',
    )}>
      <div className="shrink-0 border-b border-ink-200 bg-white px-4 pb-3 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-2xs font-bold uppercase tracking-[0.16em] text-accent-700">Рабочий список</p>
            <h2 className="mt-1 text-base font-bold tracking-tight text-ink-900">Мои заявки</h2>
          </div>
          <Count value={primaryThreads.length} label="Количество заявок с перепиской" />
        </div>
        <TextField
          id="messages-search"
          label="Поиск по поставщику, заявке, теме или адресу"
          type="search"
          value={searchInput}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Поиск по заявке или поставщику"
          icon={Search}
          className="mt-3"
        />
        <div className="mt-3 flex items-center gap-4" role="group" aria-label="Фильтр по статусу">
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
                      <span className="shrink-0 text-2xs font-medium text-ink-500">{formatRelativeDate(group.lastMessageAt)}</span>
                    </button>
                    <Link
                      to={`/requests/${group.requestId}`}
                      title="Открыть заявку"
                      className="inline-flex min-h-10 shrink-0 items-center rounded px-1.5 py-0.5 text-xs font-medium text-accent-600 hover:bg-accent-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"
                    >
                      Открыть
                    </Link>
                    {draggedInboxId != null && dropTargetRequestId === group.requestId && <span className="hidden shrink-0 text-2xs font-semibold text-accent-700 sm:inline">Отпустите для привязки</span>}
                  </div>

                  {!isCollapsed && group.threads.map((thread) => {
                    const key = thread.manual_inbox_id != null
                      ? `manual:${thread.manual_inbox_id}`
                      : `${thread.request_id}:${thread.supplier_id}`;
                    const isSelected = selectedThreadKey === key;
                    // Подсвечиваем непрочитанное, а не «когда-либо отвечал»:
                    // иначе отметка не гаснет после открытия письма.
                    const isUnread = thread.unread_count > 0;
                    const status = getThreadDisplayStatus(thread);
                    const supplierLabel = displayCorrespondenceSupplierName(thread.supplier_name) || 'Поставщик не определён';
                    return (
                      <div key={key} className={cn('border-b border-ink-100', isSelected ? 'bg-accent-50/60' : 'hover:bg-ink-50')}>
                        <button
                          type="button"
                          onClick={() => onSelectThread(thread)}
                          aria-label={`${supplierLabel}: ${thread.subject}. ${status.label}`}
                          className={cn(
                            'min-w-0 w-full border-l-2 px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-400',
                            isSelected ? 'border-accent-500' : 'border-transparent'
                          )}
                        >
                          <div className="flex items-start gap-2.5">
                            <span
                              title={isUnread ? 'Непрочитанный ответ поставщика' : undefined}
                              className={cn('mt-1.5 block h-1.5 w-1.5 shrink-0 rounded-full', isUnread ? 'bg-emerald-500' : 'bg-ink-200')}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex items-start justify-between gap-2">
                                <span className={cn('min-w-0 truncate text-sm', isUnread ? 'font-semibold text-ink-900' : 'font-medium text-ink-700')} title={thread.supplier_name || undefined}>
                                  {supplierLabel}
                                </span>
                                <span className="shrink-0 text-2xs text-ink-500">{formatRelativeDate(thread.last_message_at)}</span>
                              </div>
                              <p className="mt-1 truncate text-xs text-ink-500">
                                {thread.subject}
                                {thread.manual_inbox_id != null && <span className="ml-1.5 text-accent-600">· вручную</span>}
                              </p>
                              <div className="mt-2 flex items-center gap-1.5 text-2xs font-medium text-ink-500">
                                <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', status.tone === 'success' ? 'bg-emerald-500' : status.tone === 'warning' ? 'bg-amber-500' : status.tone === 'danger' ? 'bg-rose-500' : 'bg-ink-300')} />
                                <span title={status.title}>{status.label}</span>
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
