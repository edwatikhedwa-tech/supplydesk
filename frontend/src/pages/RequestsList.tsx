import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ChevronDown, ClipboardList, Plus, Search, SlidersHorizontal, X } from 'lucide-react';
import { api } from '@/lib/api';
import { formatRelativeDate } from '@/lib/utils';
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
  { key: 'completed', label: 'Завершённые' },
  { key: 'error', label: 'Ошибки' },
];

type SortKey = 'date' | 'status' | 'title';
const SORTS: { key: SortKey; label: string }[] = [
  { key: 'date', label: 'По дате' },
  { key: 'status', label: 'По статусу' },
  { key: 'title', label: 'По названию' },
];

/** A deadline within a week (or already past) is worth colouring — that's the
 * point of having entered one. Anything further out stays neutral. */
function isDeadlineSoon(deadline: string): boolean {
  const due = new Date(deadline).getTime();
  if (Number.isNaN(due)) return false;
  return due - Date.now() < 7 * 86400000;
}

export function RequestsList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [requests, setRequests] = useState<RequestListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const filter = (searchParams.get('filter') as FilterKey) || 'all';
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('date');
  const [sortOpen, setSortOpen] = useState(false);

  useEffect(() => {
    api
      .listRequests()
      .then((res) => setRequests(res.items))
      .finally(() => setLoading(false));
  }, []);

  const counts = useMemo(() => {
    const byStatus: Record<FilterKey, number> = { all: requests.length, draft: 0, searching: 0, updating: 0, completed: 0, error: 0 };
    requests.forEach((r) => { byStatus[r.status] += 1; });
    return byStatus;
  }, [requests]);

  const visibleRequests = useMemo(() => {
    let list = requests;
    if (filter !== 'all') list = list.filter((r) => r.status === filter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((r) => r.name.toLowerCase().includes(q) || String(r.id).includes(q));
    }
    const sorted = [...list];
    if (sort === 'date') sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    else if (sort === 'title') sorted.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    else if (sort === 'status') sorted.sort((a, b) => a.status.localeCompare(b.status));
    return sorted;
  }, [requests, filter, search, sort]);

  const currentSort = SORTS.find((s) => s.key === sort)!;
  const hasAnyRequests = requests.length > 0;

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-ink-400">Загрузка…</div>;
  }

  return (
    <div className="min-h-screen px-6 py-7 lg:px-10 lg:py-10 animate-fade-in">
      <div className="mx-auto max-w-[1600px] space-y-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <h1 className="text-[28px] font-bold tracking-tight">Мои заявки</h1>
            <p className="mt-1 text-sm text-ink-500">Все запросы на поставщиков — в одном списке.</p>
          </div>
          <button
            onClick={() => navigate('/requests/new')}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent-600 px-5 py-3 text-sm font-bold text-white shadow-panel transition hover:-translate-y-0.5 hover:bg-accent-700 hover:shadow-float"
          >
            <Plus size={18} />Новая заявка
          </button>
        </div>

        <section className="overflow-hidden rounded-2xl border border-ink-200/80 bg-white shadow-soft">
          <div className="flex flex-col gap-3 border-b border-ink-100 px-6 py-4">
            <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
              <div className="flex flex-wrap items-center gap-1.5">
                {FILTERS.map((f) => {
                  const active = f.key === filter;
                  return (
                    <button
                      key={f.key}
                      onClick={() => setSearchParams(f.key === 'all' ? {} : { filter: f.key })}
                      className={[
                        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all',
                        active ? 'bg-ink-800 text-white shadow-sm' : 'bg-ink-100/70 text-ink-600 hover:bg-ink-200/70 hover:text-ink-800',
                      ].join(' ')}
                    >
                      {f.label}
                      <span className={['rounded-full px-1.5 py-px text-2xs font-semibold tabular-nums', active ? 'bg-white/20 text-white' : 'bg-white text-ink-500'].join(' ')}>
                        {counts[f.key]}
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-400" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Поиск по названию…"
                    className="h-8 w-56 rounded-lg border border-ink-200 bg-ink-50/60 pl-8 pr-7 text-xs text-ink-700 placeholder:text-ink-400 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
                  />
                  {search && (
                    <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-600">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                <div className="relative">
                  <button
                    onClick={() => setSortOpen((v) => !v)}
                    onBlur={() => setTimeout(() => setSortOpen(false), 120)}
                    className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-ink-200 bg-white px-2.5 text-xs font-medium text-ink-600 transition-all hover:border-ink-300 hover:text-ink-800"
                  >
                    <SlidersHorizontal className="h-3.5 w-3.5 text-ink-400" />{currentSort.label}<ChevronDown className="h-3 w-3 text-ink-400" />
                  </button>
                  {sortOpen && (
                    <div className="absolute right-0 top-9 z-20 w-40 animate-scale-in rounded-lg border border-ink-200 bg-white py-1 shadow-panel">
                      {SORTS.map((s) => (
                        <button
                          key={s.key}
                          onMouseDown={() => { setSort(s.key); setSortOpen(false); }}
                          className={`block w-full px-3 py-1.5 text-left text-xs transition-colors hover:bg-ink-50 ${s.key === sort ? 'font-medium text-accent-600' : 'text-ink-600'}`}
                        >
                          {s.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {visibleRequests.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 px-6 py-20 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-50 text-accent-600">
                <ClipboardList size={22} />
              </div>
              {hasAnyRequests ? (
                <>
                  <h3 className="text-base font-bold text-ink-900">Ничего не найдено</h3>
                  <p className="max-w-sm text-sm text-ink-500">Попробуйте изменить фильтр или поисковый запрос.</p>
                </>
              ) : (
                <>
                  <h3 className="text-base font-bold text-ink-900">Заявок пока нет</h3>
                  <p className="max-w-sm text-sm text-ink-500">Создайте первую заявку, чтобы начать поиск поставщиков.</p>
                  <button
                    onClick={() => navigate('/requests/new')}
                    className="mt-2 inline-flex items-center gap-2 rounded-xl bg-accent-600 px-4 py-2.5 text-xs font-bold text-white shadow-soft transition hover:bg-accent-700"
                  >
                    <Plus size={16} />Новая заявка
                  </button>
                </>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left">
                {/* Widths are explicit so the short columns pack tight and only
                    the name column absorbs slack — otherwise the browser spreads
                    the leftover width across every column and opens a gap
                    between the name and the status badge. */}
                <thead>
                  <tr className="border-b border-ink-200 bg-ink-50 text-[11px] font-semibold uppercase tracking-wider text-ink-600">
                    <th className="w-full px-6 py-3.5">Название</th>
                    <th className="w-32 px-4 py-3.5">Статус</th>
                    <th className="w-28 px-4 py-3.5">Создана</th>
                    <th className="w-28 px-4 py-3.5">Дедлайн</th>
                    <th className="w-20 px-4 py-3.5 text-right">Позиций</th>
                    <th className="w-24 px-4 py-3.5 text-right">Поставщиков</th>
                    <th className="w-20 px-4 py-3.5 text-right">Ответов</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {visibleRequests.map((request) => (
                    <tr
                      key={request.id}
                      onClick={() => navigate(`/requests/${request.id}`)}
                      className="group cursor-pointer transition hover:bg-accent-50/40"
                    >
                      <td className="px-6 py-4">
                        <Link to={`/requests/${request.id}`} onClick={(e) => e.stopPropagation()} className="block">
                          <div className="text-[13px] font-bold text-ink-800 group-hover:text-accent-700">{request.name}</div>
                          <div className="mt-1 text-[11px] text-ink-500">#{request.id}</div>
                        </Link>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${REQUEST_STATUS_META[request.status].className}`}>
                          {REQUEST_STATUS_META[request.status].label}
                        </span>
                      </td>
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
                      <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.positions_count}</td>
                      <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.suppliers_count}</td>
                      <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.replies_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
