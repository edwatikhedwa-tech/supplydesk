import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowUpRight, ClipboardList, Plus, Search, SlidersHorizontal, X } from 'lucide-react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, api } from '@/lib/api';
import { formatRelativeDate, pluralize } from '@/lib/utils';
import { PageFrame, PageIntro } from '@/components/PageFrame';
import { Button, ErrorState, Input, Select } from '@/components/ui';
import type { RequestListItem, RequestStatus } from '@/lib/types';

const REQUEST_STATUS_META: Record<RequestStatus, { label: string; className: string }> = {
  draft: { label: 'Черновик', className: 'bg-ink-100 text-ink-600' },
  searching: { label: 'В поиске', className: 'bg-accent-50 text-accent-700' },
  updating: { label: 'Обновляется', className: 'bg-accent-50 text-accent-700' },
  completed: { label: 'Завершена', className: 'bg-emerald-50 text-emerald-700' },
  error: { label: 'Ошибка', className: 'bg-rose-50 text-rose-700' },
};

type FilterKey = 'all' | RequestStatus;
const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'draft', label: 'Черновики' },
  { key: 'searching', label: 'В поиске' },
  { key: 'updating', label: 'Обновляется' },
  { key: 'completed', label: 'Завершённые' },
  { key: 'error', label: 'Ошибки' },
];

type SortKey = 'date' | 'status' | 'title';
const SORTS: { key: SortKey; label: string }[] = [
  { key: 'date', label: 'По дате' },
  { key: 'status', label: 'По статусу' },
  { key: 'title', label: 'По названию' },
];

const STATUS_SORT_ORDER: Record<RequestStatus, number> = {
  error: 0,
  updating: 1,
  searching: 2,
  draft: 3,
  completed: 4,
};

const FILTER_KEYS = new Set<FilterKey>(FILTERS.map(({ key }) => key));
const SORT_KEYS = new Set<SortKey>(SORTS.map(({ key }) => key));

/** A deadline within a week (or already past) is worth colouring — that's the
 * point of having entered one. Anything further out stays neutral. */
function isDeadlineSoon(deadline: string): boolean {
  const due = new Date(deadline).getTime();
  if (Number.isNaN(due)) return false;
  return due - Date.now() < 7 * 86400000;
}

function getFilter(value: string | null): FilterKey {
  return value && FILTER_KEYS.has(value as FilterKey) ? value as FilterKey : 'all';
}

function getSort(value: string | null): SortKey {
  return value && SORT_KEYS.has(value as SortKey) ? value as SortKey : 'date';
}

function RequestErrorNote({ request, className = '', compact = false }: { request: RequestListItem; className?: string; compact?: boolean }) {
  if (request.status !== 'error') return null;
  const message = request.last_error || 'Поиск завершился с ошибкой. Откройте заявку, чтобы проверить детали.';
  return (
    <div
      role="alert"
      className={`flex min-w-0 items-center gap-2 rounded-lg border border-rose-100 bg-rose-50 text-rose-700 ${compact ? 'px-2.5 py-1.5 text-[11px] leading-4' : 'px-3 py-2 text-xs leading-4'} ${className}`}
    >
      <AlertTriangle size={15} className="shrink-0" />
      <span className="min-w-0 break-words" title={compact ? `Нужна проверка. ${message}` : undefined}>
        <span className="font-bold">Нужна проверка.</span>{' '}
        {message}
      </span>
    </div>
  );
}

function RequestStatus({ request }: { request: RequestListItem }) {
  const meta = REQUEST_STATUS_META[request.status];
  return <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${meta.className}`}>{meta.label}</span>;
}

function RequestCard({ request }: { request: RequestListItem }) {
  return (
    <Link
      to={`/requests/${request.id}`}
      className="block px-5 py-5 transition hover:bg-accent-50/40 focus-visible:relative focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500 sm:px-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="break-words text-sm font-bold text-ink-800">{request.name}</div>
          <div className="mt-1 text-xs text-ink-500">
            #{request.id} · {formatRelativeDate(request.created_at)} · {request.positions_count} {pluralize(request.positions_count, 'позиция', 'позиции', 'позиций')}
          </div>
        </div>
        <RequestStatus request={request} />
      </div>

      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 text-xs sm:grid-cols-4">
        <div>
          <div className="text-ink-600">Поставщики</div>
          <div className="mt-1 font-bold tabular-nums text-ink-700">{request.suppliers_count}</div>
        </div>
        <div>
          <div className="text-ink-600">Ответы</div>
          <div className="mt-1 font-bold tabular-nums text-ink-700">{request.replies_count}</div>
        </div>
        <div>
          <div className="text-ink-600">Дедлайн</div>
          <div className={`mt-1 font-semibold ${request.deadline && isDeadlineSoon(request.deadline) ? 'text-rose-600' : 'text-ink-600'}`}>
            {request.deadline ? new Date(request.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '—'}
          </div>
        </div>
        <div className="flex items-end justify-end">
          <span className="inline-flex items-center gap-1 text-xs font-bold text-accent-700">
            Открыть <ArrowUpRight size={14} />
          </span>
        </div>
      </div>
      <RequestErrorNote request={request} className="mt-4" />
    </Link>
  );
}

function RequestsLoading() {
  return (
    <PageFrame role="status" aria-busy="true" aria-label="Загрузка заявок">
      <div className="space-y-6">
        <div className="space-y-3">
          <div className="skeleton h-8 w-48 rounded-lg" />
          <div className="skeleton h-4 w-96 max-w-full rounded" />
        </div>
        <div className="overflow-hidden rounded-2xl border border-ink-200/80 bg-white shadow-soft">
          <div className="skeleton h-24 border-b border-ink-100" />
          <div className="space-y-3 p-5 sm:p-6">
            {[1, 2, 3, 4].map((item) => <div key={item} className="skeleton h-16 rounded-xl" />)}
          </div>
        </div>
      </div>
    </PageFrame>
  );
}

function RequestsError({ message, onRetry, retrying }: { message: string; onRetry: () => void; retrying: boolean }) {
  return <PageFrame><ErrorState title="Не удалось загрузить заявки" message={message} retryLabel="Повторить загрузку" onRetry={onRetry} retrying={retrying} /></PageFrame>;
}

export function RequestsList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [requests, setRequests] = useState<RequestListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const filter = getFilter(searchParams.get('filter'));
  const search = searchParams.get('q') || '';
  const sort = getSort(searchParams.get('sort'));

  const load = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const res = await api.listRequests();
      setRequests(res.items);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'Проверьте соединение и попробуйте ещё раз.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setToolbarParam = (key: 'filter' | 'q' | 'sort', value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  const counts = useMemo(() => {
    const byStatus: Record<FilterKey, number> = { all: requests.length, draft: 0, searching: 0, updating: 0, completed: 0, error: 0 };
    requests.forEach((request) => { byStatus[request.status] += 1; });
    return byStatus;
  }, [requests]);

  const visibleRequests = useMemo(() => {
    let list = requests;
    if (filter !== 'all') list = list.filter((request) => request.status === filter);
    if (search.trim()) {
      const query = search.trim().toLowerCase();
      list = list.filter((request) => request.name.toLowerCase().includes(query) || String(request.id).includes(query));
    }
    const sorted = [...list];
    if (sort === 'date') {
      sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    } else if (sort === 'title') {
      sorted.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    } else {
      sorted.sort((a, b) => STATUS_SORT_ORDER[a.status] - STATUS_SORT_ORDER[b.status] || new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }
    return sorted;
  }, [requests, filter, search, sort]);

  const hasAnyRequests = requests.length > 0;
  const hasActiveView = filter !== 'all' || Boolean(search.trim());

  if (loading) return <RequestsLoading />;
  if (errorMessage) {
    return <RequestsError message={errorMessage} onRetry={() => { void load(); }} retrying={loading} />;
  }

  return (
    <PageFrame className="dashboard-shell">
      <div className="space-y-6">
        <PageIntro
          eyebrow="Рабочее пространство"
          title="Мои заявки"
          description={`${requests.length} ${pluralize(requests.length, 'заявка', 'заявки', 'заявок')} · ${counts.error} ${pluralize(counts.error, 'ошибка', 'ошибки', 'ошибок')}`}
          actions={<Button onClick={() => navigate('/requests/new')} variant="primary"><Plus size={18} />Новая заявка</Button>}
        />

        <section className="sd-table-shell" aria-label="Список заявок">
            <div className="flex flex-col gap-4 border-b border-ink-100 px-5 py-4 sm:px-6 xl:flex-row xl:items-center xl:justify-between xl:gap-6">
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Фильтр заявок">
              {FILTERS.map((item) => {
                const active = item.key === filter;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setToolbarParam('filter', item.key === 'all' ? '' : item.key)}
                    aria-pressed={active}
                    className={[
                      'inline-flex min-h-8 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-1',
                      active ? 'bg-ink-800 text-white shadow-sm' : 'bg-ink-100/70 text-ink-600 hover:bg-ink-200/70 hover:text-ink-800',
                    ].join(' ')}
                  >
                    {item.label}
                    <span className={['rounded-full px-1.5 py-px text-2xs font-semibold tabular-nums', active ? 'bg-white/20 text-white' : 'bg-white text-ink-500'].join(' ')}>
                      {counts[item.key]}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-1 gap-2 sm:flex sm:items-center sm:justify-end">
              <div className="relative min-w-0 sm:w-64">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-400" />
                <Input
                  id="request-search"
                  aria-label="Поиск заявок по названию или номеру"
                  value={search}
                  onChange={(event) => setToolbarParam('q', event.target.value)}
                  placeholder="Поиск по названию или №…"
                  className="h-10 pl-8 pr-8 text-xs"
                />
                {search && (
                  <button
                    type="button"
                    aria-label="Очистить поиск"
                    onClick={() => setToolbarParam('q', '')}
                    className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-ink-400 hover:bg-ink-100 hover:text-ink-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>

              <div className="flex min-w-0 items-center gap-1.5 sm:min-w-[132px]">
                <SlidersHorizontal className="h-3.5 w-3.5 shrink-0 text-ink-400" aria-hidden="true" />
                <Select aria-label="Сортировка заявок" value={sort} onChange={(event) => setToolbarParam('sort', event.target.value)} className="text-xs font-medium">
                  {SORTS.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
                </Select>
              </div>
            </div>
          </div>

          {visibleRequests.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 px-6 py-20 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-50 text-accent-600">
                <ClipboardList size={22} />
              </div>
              {hasAnyRequests && hasActiveView ? (
                <>
                  <h3 className="text-base font-bold text-ink-900">Ничего не найдено</h3>
                  <p className="max-w-sm text-sm text-ink-500">Попробуйте изменить фильтр или поисковый запрос.</p>
                  <button
                    type="button"
                    onClick={() => setSearchParams({}, { replace: true })}
                    className="mt-2 inline-flex min-h-10 items-center rounded-lg border border-ink-200 px-4 py-2.5 text-xs font-bold text-ink-700 transition hover:border-ink-300 hover:bg-ink-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
                  >
                    Сбросить фильтры
                  </button>
                </>
              ) : (
                <>
                  <h3 className="text-base font-bold text-ink-900">Заявок пока нет</h3>
                  <p className="max-w-sm text-sm text-ink-500">Создайте первую заявку, чтобы начать поиск поставщиков.</p>
                  <button
                    type="button"
                    onClick={() => navigate('/requests/new')}
                    className="mt-2 inline-flex min-h-10 items-center gap-2 rounded-xl bg-accent-600 px-4 py-2.5 text-xs font-bold text-white shadow-soft transition hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
                  >
                    <Plus size={16} />Новая заявка
                  </button>
                </>
              )}
            </div>
          ) : (
            <>
              <div className="divide-y divide-ink-100 min-[1536px]:hidden">
                {visibleRequests.map((request) => <RequestCard key={request.id} request={request} />)}
              </div>
              <div className="hidden overflow-x-auto min-[1536px]:block">
                <table className="w-full min-w-[1040px] table-fixed text-left">
                  <colgroup>
                    <col />
                    <col className="w-28" />
                    <col className="w-24" />
                    <col className="w-24" />
                    <col className="w-20" />
                    <col className="w-28" />
                    <col className="w-24" />
                  </colgroup>
                  <thead>
                    <tr className="border-b border-ink-200 bg-ink-50 text-2xs font-semibold uppercase tracking-wider text-ink-600">
                      <th scope="col" className="w-full px-6 py-3.5">Название</th>
                      <th scope="col" className="w-28 px-4 py-3.5">Статус</th>
                      <th scope="col" className="w-24 px-4 py-3.5">Создана</th>
                      <th scope="col" className="w-24 px-4 py-3.5">Дедлайн</th>
                      <th scope="col" className="w-20 px-4 py-3.5 text-center">Позиций</th>
                      <th scope="col" className="w-24 px-4 py-3.5 text-center">Поставщиков</th>
                      <th scope="col" className="w-24 px-4 py-3.5 pr-8 text-center">Ответов</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {visibleRequests.map((request) => (
                      <tr key={request.id} className="group transition hover:bg-accent-50/40">
                        <td className="px-6 py-4 align-middle">
                          <div className={request.status === 'error' ? 'grid min-w-0 grid-cols-[150px_minmax(0,1fr)] items-center gap-5' : ''}>
                            <Link to={`/requests/${request.id}`} className="block min-w-0 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2">
                              <div className="break-words text-sm font-bold text-ink-800 group-hover:text-accent-700">{request.name}</div>
                              <div className="mt-1 text-xs text-ink-500">#{request.id}</div>
                            </Link>
                            <RequestErrorNote request={request} compact className="w-full max-w-[620px] justify-start" />
                          </div>
                        </td>
                        <td className="px-4 py-4"><RequestStatus request={request} /></td>
                        <td className="whitespace-nowrap px-4 py-4 text-xs text-ink-500" title={new Date(request.created_at).toLocaleString('ru-RU')}>
                          {formatRelativeDate(request.created_at)}
                        </td>
                        <td className="whitespace-nowrap px-4 py-4 text-xs">
                          {request.deadline ? (
                            <span className={isDeadlineSoon(request.deadline) ? 'font-semibold text-rose-600' : 'text-ink-600'}>
                              {new Date(request.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                            </span>
                          ) : (
                            <span className="text-ink-300">—</span>
                          )}
                        </td>
                        <td className="px-4 py-4 text-center text-sm font-semibold tabular-nums text-ink-700">{request.positions_count}</td>
                        <td className="px-4 py-4 text-center text-sm font-semibold tabular-nums text-ink-700">{request.suppliers_count}</td>
                        <td className="w-24 px-4 py-4 pr-8 text-center text-sm font-semibold tabular-nums text-ink-700">{request.replies_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      </div>
    </PageFrame>
  );
}
