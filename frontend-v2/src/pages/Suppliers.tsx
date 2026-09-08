import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import clsx from 'clsx';
import { Ban, Search, Star, Truck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { now, formatCompanyName, formatPercent, formatRelativeTime } from '../lib/format';
import type { GlobalSupplierSummary } from '../lib/types';
import { useApiData } from '../lib/useApiData';

type FilterKey = 'all' | 'favorite' | 'blacklisted' | 'stale' | 'never_replied' | 'not_contacted';

const filterConfig: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'favorite', label: 'Избранные' },
  { key: 'blacklisted', label: 'Чёрный список' },
  { key: 'stale', label: 'Давно не было контакта' },
  { key: 'never_replied', label: 'Не отвечают' },
  { key: 'not_contacted', label: 'Не контактировали' },
];

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  return Math.round((now().getTime() - new Date(iso).getTime()) / 86400000);
}

function matchesFilter(s: GlobalSupplierSummary, filter: FilterKey): boolean {
  switch (filter) {
    case 'favorite':
      return s.relationship_status === 'favorite';
    case 'blacklisted':
      return s.relationship_status === 'blacklisted';
    case 'stale': {
      const d = daysSince(s.last_contact_at);
      return d !== null && d > 14;
    }
    case 'never_replied':
      return s.total_requests > 0 && s.response_rate === 0;
    case 'not_contacted':
      return s.total_requests === 0;
    default:
      return true;
  }
}

const columnHelper = createColumnHelper<GlobalSupplierSummary>();

export function Suppliers() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterKey>('all');
  const [sorting, setSorting] = useState<SortingState>([{ id: 'total_requests', desc: true }]);

  const state = useApiData(() => api.listGlobalSuppliers().then((r) => r.items), []);
  const suppliers = state.status === 'ready' ? state.data : [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return suppliers.filter((s) => {
      if (!matchesFilter(s, filter)) return false;
      if (!q) return true;
      return (
        s.name.toLowerCase().includes(q) ||
        s.categories.some((c) => c.toLowerCase().includes(q)) ||
        s.inn.includes(q)
      );
    });
  }, [suppliers, search, filter]);

  const counts = useMemo(
    () =>
      Object.fromEntries(filterConfig.map((f) => [f.key, suppliers.filter((s) => matchesFilter(s, f.key)).length])) as Record<
        FilterKey,
        number
      >,
    [suppliers],
  );

  const columns = useMemo(
    () => [
      columnHelper.accessor('name', {
        header: 'Компания',
        cell: (ctx) => (
          <div className="min-w-0">
            <p className="truncate font-medium text-ink">{formatCompanyName(ctx.getValue())}</p>
            <p className="truncate text-[11.5px] text-ink-muted">
              ИНН {ctx.row.original.inn} · {ctx.row.original.site}
            </p>
          </div>
        ),
      }),
      columnHelper.accessor('total_requests', {
        header: 'Заявки',
        cell: (ctx) => <span className="tabular-nums text-ink-soft">{ctx.getValue()}</span>,
      }),
      columnHelper.accessor('response_rate', {
        header: 'Отвечаемость',
        cell: (ctx) => {
          const rate = ctx.getValue();
          const total = ctx.row.original.total_requests;
          if (total === 0) return <span className="text-ink-faint">—</span>;
          const tone = rate >= 70 ? 'success' : rate > 0 ? 'warning' : 'danger';
          return (
            <div className="flex items-center gap-1.5">
              <Badge tone={tone}>{formatPercent(rate / 100)}</Badge>
              {ctx.row.original.avg_response_hours != null && (
                <span className="text-[11px] text-ink-faint">~{ctx.row.original.avg_response_hours} ч</span>
              )}
            </div>
          );
        },
      }),
      columnHelper.accessor('last_contact_at', {
        header: 'Последний контакт',
        cell: (ctx) => {
          const v = ctx.getValue();
          return <span className="text-ink-muted">{v ? formatRelativeTime(v) : 'Не было'}</span>;
        },
      }),
      columnHelper.accessor('relationship_status', {
        header: 'Отношения',
        cell: (ctx) => {
          const status = ctx.getValue();
          if (status === 'favorite')
            return (
              <Badge tone="accent">
                <Star size={10} className="fill-current" /> Избранный
              </Badge>
            );
          if (status === 'blacklisted')
            return (
              <span title={ctx.row.original.blacklist_reason ?? undefined}>
                <Badge tone="danger">
                  <Ban size={10} /> Чёрный список
                </Badge>
              </span>
            );
          return <span className="text-ink-faint">—</span>;
        },
      }),
    ],
    [],
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
        title="Поставщики"
        description={state.status === 'ready' ? `${suppliers.length} компаний в общей картотеке` : 'Загружаем поставщиков…'}
      />

      <div className="flex flex-wrap items-center gap-3 border-b border-border px-6 pb-3">
        <div className="relative w-72">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Поиск поставщиков по компании, продукции или ИНН"
            placeholder="Компания, продукция или ИНН…"
            className="h-8 w-full rounded-md border border-border-strong bg-surface pl-8 pr-3 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1">
          {filterConfig.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={clsx(
                'rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors',
                filter === f.key ? 'bg-accent-subtle text-accent' : 'text-ink-muted hover:bg-surface-hover hover:text-ink-soft',
              )}
            >
              {f.label}
              <span className="ml-1 tabular-nums text-ink-faint">{counts[f.key]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {state.status === 'loading' ? (
          <LoadingState label="Загружаем поставщиков с бэкенда…" />
        ) : state.status === 'error' ? (
          <ErrorState message={state.message} onRetry={state.reload} />
        ) : filtered.length === 0 ? (
          <EmptyState icon={Truck} title="Поставщики не найдены" description="Попробуйте другой запрос или фильтр." />
        ) : (
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="sticky top-0 z-10 bg-canvas">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-border">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className="cursor-pointer select-none whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted first:pl-6 last:pr-6"
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => navigate(`/suppliers/${row.original.id}`)}
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
        )}
      </div>
    </div>
  );
}
