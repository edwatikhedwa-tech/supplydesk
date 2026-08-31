import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Clock3, Mail, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import { cn, formatRelativeDate, pluralize } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';
import { getThreadDisplayStatus, isAwaitingResponse, isPrimaryCorrespondence, needsThreadAttention } from '@/components/mail/threadStatus';

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
}

type ThreadFilter = 'primary' | 'awaiting-response';

export function ThreadList({ selectedThreadKey, onSelectThread, refreshKey }: ThreadListProps) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryToken, setRetryToken] = useState(0);
  const [search, setSearch] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [filter, setFilter] = useState<ThreadFilter>('primary');

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

  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(value), 200);
  };

  const searchedThreads = useMemo(() => {
    if (!search.trim()) return threads;
    const q = search.trim().toLowerCase();
    return threads.filter(
      (t) =>
        t.subject.toLowerCase().includes(q) ||
        t.request_name.toLowerCase().includes(q) ||
        t.supplier_name.toLowerCase().includes(q) ||
        t.supplier_email.toLowerCase().includes(q)
    );
  }, [threads, search]);

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
  const searching = Boolean(search.trim());
  const narrowing = searching || filter !== 'primary';

  return (
    <div className={cn(
      'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[360px] xl:flex',
      selectedThreadKey ? 'hidden' : 'flex',
    )}>
      <div className="px-3 pt-3 pb-2.5 border-b border-ink-100 shrink-0">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <label htmlFor="messages-search" className="sr-only">Поиск по поставщику, заявке или письму</label>
          <input
            id="messages-search"
            type="text"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по поставщику, заявке или письму..."
            className="w-full pl-9 pr-3 py-2 text-sm bg-ink-50 border border-ink-200 rounded-lg focus:outline-none focus:border-ink-300 focus:bg-white transition-colors placeholder:text-ink-400"
          />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Фильтр по статусу">
          <button
            type="button"
            aria-pressed={filter === 'primary'}
            onClick={() => setFilter('primary')}
            className={cn(
              'inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400',
              filter === 'primary' ? 'bg-ink-800 text-white shadow-sm' : 'bg-ink-100 text-ink-600 hover:bg-ink-200 hover:text-ink-800',
            )}
          >
            Отправленные и ответы
            <span className={cn('rounded-full px-1.5 py-px text-2xs tabular-nums', filter === 'primary' ? 'bg-white/20 text-white' : 'bg-white text-ink-500')}>
              {primaryThreads.length}
            </span>
          </button>
          <button
            type="button"
            aria-pressed={filter === 'awaiting-response'}
            onClick={() => setFilter('awaiting-response')}
            className={cn(
              'inline-flex min-h-9 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400',
              filter === 'awaiting-response' ? 'bg-accent-700 text-white shadow-sm' : 'bg-accent-50 text-accent-800 ring-1 ring-accent-200 hover:bg-accent-100',
            )}
          >
            <Clock3 size={13} aria-hidden="true" />
            Ожидает ответа
            <span className={cn('rounded-full px-1.5 py-px text-2xs tabular-nums', filter === 'awaiting-response' ? 'bg-white/20 text-white' : 'bg-white text-accent-700')}>
              {awaitingCount}
            </span>
          </button>
        </div>
      </div>

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
                : search.trim()
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
                  <div className="flex items-center gap-1 px-2 py-1.5 sticky top-0 z-10 bg-white/95 backdrop-blur-sm">
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
                    return (
                      <button
                        key={key}
                        onClick={() => onSelectThread(thread)}
                        aria-label={`${thread.supplier_name || 'Поставщик не определён'}: ${thread.subject}. ${status.label}`}
                        className={cn(
                          'w-full border-l-2 py-2.5 pl-7 pr-3 text-left transition-colors',
                          isSelected ? 'bg-accent-50/50 border-accent-500' : 'border-transparent hover:bg-ink-50'
                        )}
                      >
                        <div className="flex items-start gap-2">
                          <span
                            title={isUnread ? 'Непрочитанный ответ поставщика' : undefined}
                            className={cn('mt-1.5 block h-2 w-2 shrink-0 rounded-full', isUnread ? 'bg-emerald-500' : 'bg-transparent')}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="mb-0.5 flex items-center justify-between gap-2">
                              <span className={cn('truncate text-sm', isUnread ? 'font-semibold text-ink-800' : 'font-medium text-ink-700')}>
                                {thread.supplier_name || 'Поставщик не определён'}
                              </span>
                              <span className="shrink-0 text-xs text-ink-600">{formatRelativeDate(thread.last_message_at)}</span>
                            </div>
                            <p className="truncate text-xs text-ink-500">
                              {thread.subject}
                              {thread.manual_inbox_id != null && <span className="ml-1.5 text-accent-600">· вручную</span>}
                            </p>
                            <div className="mt-1.5 flex min-w-0 items-center gap-2">
                              {!isAwaitingResponse(thread) && (
                                <span title={status.title} className={cn('inline-flex shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1', status.className)}>{status.label}</span>
                              )}
                              <span className="truncate text-xs text-ink-600">
                                {thread.messages_count} {pluralize(thread.messages_count, 'письмо', 'письма', 'писем')}
                                {hasReplies && <> · {thread.replies_count} {pluralize(thread.replies_count, 'ответ', 'ответа', 'ответов')}</>}
                              </span>
                            </div>
                          </div>
                        </div>
                      </button>
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
