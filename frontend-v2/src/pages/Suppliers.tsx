import clsx from 'clsx';
import { Ban, ExternalLink, Flame, Search, Star, Truck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { CopyButton } from '../components/ui/CopyButton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { now, checkoUrl, companyAge, formatCompanyName, formatMoney, formatPercent, formatRelativeTime } from '../lib/format';
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

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-ink-faint">{label}</p>
      <p className="text-[13px] text-ink">
        {value}
        {sub && <span className="ml-1 text-[11px] text-ink-faint">{sub}</span>}
      </p>
    </div>
  );
}

export function Suppliers() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterKey>('all');

  const state = useApiData(() => api.listGlobalSuppliers().then((r) => r.items), []);
  const suppliers = state.status === 'ready' ? state.data : [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return suppliers.filter((s) => {
      if (!matchesFilter(s, filter)) return false;
      if (!q) return true;
      return s.name.toLowerCase().includes(q) || s.inn.includes(q) || s.site.toLowerCase().includes(q);
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
            aria-label="Поиск поставщиков по компании, сайту или ИНН"
            placeholder="Компания, сайт или ИНН…"
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
          <div className="flex flex-col divide-y divide-border">
            {filtered.map((s) => {
              const age = companyAge(s.registry?.registered_at);
              const checko = checkoUrl(s.registry?.ogrn);
              return (
                <div
                  key={s.id}
                  onClick={() => navigate(`/suppliers/${s.id}`)}
                  className="flex cursor-pointer flex-col gap-3 px-6 py-4 hover:bg-surface-hover"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-[13.5px] font-semibold text-ink">
                        {formatCompanyName(s.name)}{' '}
                        <span className="inline-flex items-center gap-1 font-normal text-ink-faint">
                          ИНН {s.inn}
                          {s.inn && <CopyButton text={s.inn} />}
                        </span>
                      </p>
                      {s.site && (
                        <a
                          href={s.site.startsWith('http') ? s.site : `https://${s.site}`}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="mt-0.5 flex items-center gap-1 text-[12px] text-accent hover:underline"
                        >
                          {s.site} <ExternalLink size={10} />
                        </a>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {s.relationship_status === 'favorite' && (
                        <Badge tone="accent">
                          <Star size={10} className="fill-current" /> Избранный
                        </Badge>
                      )}
                      {s.relationship_status === 'blacklisted' && (
                        <span title={s.blacklist_reason ?? undefined}>
                          <Badge tone="danger">
                            <Ban size={10} /> Чёрный список
                          </Badge>
                        </span>
                      )}
                      {s.registry && (
                        <span className={`text-[11px] ${s.registry.is_active === false ? 'text-danger' : 'text-success'}`}>
                          {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
                        </span>
                      )}
                      {checko && (
                        <a
                          href={checko}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          title="Профиль на Checko"
                          className="flex h-6 w-6 items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover hover:text-ink-soft"
                        >
                          <Flame size={13} />
                        </a>
                      )}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-4">
                    <Stat label="Возраст" value={age ?? '—'} />
                    <Stat
                      label="Выручка"
                      value={formatMoney(s.finances?.revenue ?? null)}
                      sub={s.finances?.report_year ? `за ${s.finances.report_year}` : undefined}
                    />
                    <Stat label="Прибыль" value={formatMoney(s.finances?.profit ?? null)} />
                    <Stat label="Заявок" value={String(s.total_requests)} />
                    <Stat label="Отклик" value={s.total_requests > 0 ? formatPercent(s.response_rate / 100) : '—'} />
                    <Stat label="Последний контакт" value={s.last_contact_at ? formatRelativeTime(s.last_contact_at) : 'Не было'} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
