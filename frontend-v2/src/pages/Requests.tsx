import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import clsx from 'clsx';
import { ArrowUpDown, Plus, Search, Truck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { NewRequestModal } from '../components/NewRequestModal';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { formatRelativeTime } from '../lib/format';
import { requestStatusMeta } from '../lib/statusMeta';
import type { RequestListItem, RequestStatus } from '../lib/types';
import { useApiData } from '../lib/useApiData';

const statusFilters: { key: RequestStatus | 'all'; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'searching', label: 'Идёт поиск' },
  { key: 'updating', label: 'Ожидание ответов' },
  { key: 'draft', label: 'Черновики' },
  { key: 'completed', label: 'Завершённые' },
  { key: 'error', label: 'Ошибки' },
];

const columnHelper = createColumnHelper<RequestListItem>();

export function Requests() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState(() => searchParams.get('q') ?? '');
  const [status, setStatus] = useState<RequestStatus | 'all'>('all');
  const [sorting, setSorting] = useState<SortingState>([{ id: 'deadline', desc: false }]);

  const state = useApiData(() => api.listRequests().then((r) => r.items), []);
  const requests = state.status === 'ready' ? state.data : [];

  const threadsState = useApiData(() => api.listThreads().then((r) => r.items), []);
  const unreadByRequestId = useMemo(() => {
    const map = new Map<number, number>();
    if (threadsState.status === 'ready') {
      for (const t of threadsState.data) map.set(t.request_id, (map.get(t.request_id) ?? 0) + t.unread_count);
    }
    return map;
  }, [threadsState]);

  const filtered = useMemo(() => {
    return requests.filter((r) => {
      if (status !== 'all' && r.status !== status) return false;
      if (search && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [requests, search, status]);

  const columns = useMemo(
    () => [
      columnHelper.accessor('name', {
        header: 'Заявка',
        cell: (ctx) => {
          const unread = unreadByRequestId.get(ctx.row.original.id) ?? 0;
          return (
            <div className="flex min-w-0 items-center gap-2">
              <div className="min-w-0">
                <p className="truncate font-medium text-ink">{ctx.getValue()}</p>
                <p className="truncate text-[11.5px] text-ink-muted">
                  №{ctx.row.original.id} · {ctx.row.original.sender_name}
                </p>
              </div>
              {unread > 0 && (
                <span
                  className="flex h-4 min-w-[16px] shrink-0 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white"
                  title={`Новых ответов: ${unread}`}
                >
                  {unread}
                </span>
              )}
            </div>
          );
        },
      }),
      columnHelper.accessor('suppliers_count', {
        header: 'Поставщики',
        cell: (ctx) => <span className="tabular-nums text-ink-soft">{ctx.getValue()}</span>,
      }),
      columnHelper.accessor('replies_count', {
        header: 'Ответы',
        cell: (ctx) => (
          <span className="tabular-nums text-ink-soft">
            {ctx.getValue()}/{ctx.row.original.sent_count}
          </span>
        ),
      }),
      columnHelper.accessor('search_progress', {
        header: 'Прогресс поиска',
        cell: (ctx) => {
          const total = ctx.row.original.search_total;
          const value = ctx.getValue();
          const pct = total > 0 ? Math.round((value / total) * 100) : 0;
          return total === 0 ? (
            <span className="text-ink-faint">—</span>
          ) : (
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-surface-hover">
                <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
              </div>
              <span className="tabular-nums text-[11.5px] text-ink-muted">
                {value}/{total}
              </span>
            </div>
          );
        },
      }),
      columnHelper.accessor('status', {
        header: 'Статус',
        cell: (ctx) => {
          const meta = requestStatusMeta[ctx.getValue()];
          return <Badge tone={meta.tone}>{meta.label}</Badge>;
        },
      }),
      columnHelper.accessor('deadline', {
        header: 'Дедлайн',
        cell: (ctx) => <DeadlineTag deadline={ctx.getValue()} />,
      }),
      columnHelper.accessor('updated_at', {
        header: 'Обновлено',
        cell: (ctx) => <span className="text-ink-muted">{formatRelativeTime(ctx.getValue())}</span>,
      }),
    ],
    [unreadByRequestId],
  );

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader
        title="Заявки"
        description={state.status === 'ready' ? `${requests.length} заявок в работе` : 'Загружаем заявки…'}
        actions={
          <Button variant="primary" icon={<Plus size={14} />} onClick={() => setCreating(true)}>
            Новая заявка
          </Button>
        }
      />

      {creating && (
        <NewRequestModal
          onClose={() => setCreating(false)}
          onCreated={() => state.reload()}
        />
      )}

      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 pb-3 sm:gap-3 sm:px-6">
        <div className="relative w-full sm:w-64 sm:shrink-0">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Поиск заявок по названию"
            placeholder="Поиск по названию…"
            className="h-8 w-full rounded-md border border-border-strong bg-surface pl-8 pr-3 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {statusFilters.map((f) => (
            <button
              key={f.key}
              onClick={() => setStatus(f.key)}
              className={clsx(
                'rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors',
                status === f.key ? 'bg-accent-subtle text-accent' : 'text-ink-muted hover:bg-surface-hover hover:text-ink-soft',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-w-0 flex-1 overflow-auto">
        {state.status === 'loading' ? (
          <LoadingState label="Загружаем заявки с бэкенда…" />
        ) : state.status === 'error' ? (
          <ErrorState message={state.message} onRetry={state.reload} />
        ) : filtered.length === 0 ? (
          <EmptyState icon={Truck} title="Ничего не найдено" description="Измените поиск или фильтр по статусу." />
        ) : (
          <>
          <div className="flex flex-col divide-y divide-border sm:hidden">
            {filtered.map((r) => {
              const unread = unreadByRequestId.get(r.id) ?? 0;
              const meta = requestStatusMeta[r.status];
              const pct = r.search_total > 0 ? Math.round((r.search_progress / r.search_total) * 100) : null;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => navigate(`/requests/${r.id}`)}
                  className="flex flex-col gap-1.5 px-4 py-3 text-left active:bg-surface-hover"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">{r.name}</p>
                      <p className="truncate text-[11.5px] text-ink-muted">
                        №{r.id} · {r.sender_name}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      {unread > 0 && (
                        <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                          {unread}
                        </span>
                      )}
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-ink-muted">
                    <span>
                      {r.suppliers_count} поставщиков · {r.replies_count}/{r.sent_count} ответов
                    </span>
                    {pct !== null && <span>Поиск {pct}%</span>}
                    <DeadlineTag deadline={r.deadline} />
                    <span className="ml-auto text-ink-faint">{formatRelativeTime(r.updated_at)}</span>
                  </div>
                </button>
              );
            })}
          </div>
          <table className="hidden w-full border-collapse text-[12.5px] sm:table">
            <thead className="sticky top-0 z-10 bg-canvas">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-border">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className="cursor-pointer select-none whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted first:pl-6 last:pr-6"
                    >
                      <span className="inline-flex items-center gap-1">
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getIsSorted() && <ArrowUpDown size={11} />}
                      </span>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => navigate(`/requests/${row.original.id}`)}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-hover"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2.5 align-middle first:pl-6 last:pr-6">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          </>
        )}
      </div>
    </div>
  );
}
