import clsx from 'clsx';
import { Ban, ExternalLink, Search, Star, TrendingDown, TrendingUp, Truck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { CopyButton } from '../components/ui/CopyButton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { now, checkoUrl, companyAge, formatCompanyName, formatMoney, formatPercent, formatRelativeTime } from '../lib/format';
import type { SupplierDirectoryItem } from '../lib/types';
import { useApiData } from '../lib/useApiData';

type FilterKey = 'all' | 'missing_inn' | 'favorite' | 'blacklisted' | 'stale' | 'never_replied' | 'not_contacted';

const filterConfig: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'missing_inn', label: 'Без ИНН' },
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

function matchesFilter(s: SupplierDirectoryItem, filter: FilterKey): boolean {
  switch (filter) {
    case 'missing_inn':
      return s.verification_status === 'missing_inn';
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

export function Suppliers() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterKey>('all');

  const state = useApiData(() => api.listSupplierDirectory().then((r) => r.items), []);
  const suppliers = state.status === 'ready' ? state.data : [];
  const verifiedCount = suppliers.filter((supplier) => supplier.verification_status === 'verified').length;

  const openSupplier = (supplier: SupplierDirectoryItem) => {
    if (supplier.global_supplier_id) {
      navigate(`/suppliers/${supplier.global_supplier_id}`);
    } else if (supplier.request_id) {
      navigate(`/requests/${supplier.request_id}`);
    }
  };

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
        description={
          state.status === 'ready'
            ? `${suppliers.length} поставщиков · ${verifiedCount} с подтверждённым ИНН`
            : 'Загружаем поставщиков…'
        }
      />

      <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 sm:px-6 pb-3">
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

      <div className="min-w-0 flex-1 overflow-auto">
        {state.status === 'loading' ? (
          <LoadingState label="Загружаем поставщиков с бэкенда…" />
        ) : state.status === 'error' ? (
          <ErrorState message={state.message} onRetry={state.reload} />
        ) : filtered.length === 0 ? (
          <EmptyState icon={Truck} title="Поставщики не найдены" description="Попробуйте другой запрос или фильтр." />
        ) : (
          <>
          <div className="flex flex-col divide-y divide-border xl:hidden">
            {filtered.map((s) => {
              const age = companyAge(s.registry?.registered_at);
              const profit = s.finances?.profit ?? null;
              const contact = s.site || s.email;
              return (
                <button
                  key={`${s.verification_status}-${s.id}`}
                  type="button"
                  onClick={() => openSupplier(s)}
                  className="flex flex-col gap-1.5 px-4 py-3 text-left active:bg-surface-hover"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-ink">{formatCompanyName(s.name)}</p>
                      <p className="truncate text-[11px] text-ink-muted">
                        {s.inn ? `ИНН ${s.inn}` : 'ИНН пока не найден'}{age ? ` · ${age}` : ''}{contact ? ` · ${contact}` : ''}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      {s.relationship_status === 'favorite' && (
                        <Badge tone="accent"><Star size={10} className="fill-current" /></Badge>
                      )}
                      {s.relationship_status === 'blacklisted' && (
                        <Badge tone="danger"><Ban size={10} /></Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px]">
                    {s.finances?.revenue != null && (
                      <span className="font-semibold text-ink">{formatMoney(s.finances.revenue)}</span>
                    )}
                    {profit != null && (
                      <span className={clsx('flex items-center gap-1 font-medium', profit >= 0 ? 'text-success' : 'text-danger')}>
                        {profit >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                        {formatMoney(profit)}
                      </span>
                    )}
                    <span className="text-ink-muted">
                      {s.total_requests > 0 ? `${s.total_requests} заявок · ${formatPercent(s.response_rate / 100)} отклик` : 'Не контактировали'}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
          <div className="hidden overflow-x-auto xl:block">
            <table className="w-full table-fixed border-collapse text-[12.5px]">
              <colgroup>
                <col className="w-[25%]" />
                <col className="w-[7%]" />
                <col className="w-[9%]" />
                <col className="w-[9%]" />
                <col className="w-[12%]" />
                <col className="w-[7%]" />
                <col className="w-[7%]" />
                <col className="w-[10%]" />
                <col className="w-[14%]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-canvas">
                <tr className="border-b border-border">
                  {['Название', 'Возраст', 'Выручка', 'Прибыль', 'ЕГРЮЛ', 'Заявок', 'Отклик', 'Контакт', 'Статус'].map((h) => (
                    <th key={h} className="whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted first:pl-6 last:pr-6">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => {
                  const age = companyAge(s.registry?.registered_at);
                  const checko = checkoUrl(s.registry?.ogrn);
                  const profit = s.finances?.profit ?? null;
                  return (
                    <tr key={`${s.verification_status}-${s.id}`} onClick={() => openSupplier(s)} className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-hover">
                      <td className="px-3 py-2.5 pl-6 align-middle">
                        <div className="min-w-0">
                          <p className="truncate font-medium text-ink">{formatCompanyName(s.name)}</p>
                          <p className="flex items-center gap-1 truncate text-[11px] text-ink-muted">
                            {s.inn ? `ИНН ${s.inn}` : 'ИНН пока не найден'}
                            {s.inn && <CopyButton text={s.inn} />}
                            {s.site && (
                              <a
                                href={s.site.startsWith('http') ? s.site : `https://${s.site}`}
                                target="_blank"
                                rel="noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="ml-1 flex items-center gap-0.5 text-accent hover:underline"
                              >
                                {s.site} <ExternalLink size={9} />
                              </a>
                            )}
                          </p>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 align-middle text-ink-soft">{age ?? '—'}</td>
                      <td className="px-3 py-2.5 align-middle">
                        {s.finances?.revenue != null ? (
                          <>
                            <p className="font-semibold text-ink">{formatMoney(s.finances.revenue)}</p>
                            {s.finances.report_year && <p className="text-[10.5px] text-ink-faint">за {s.finances.report_year}</p>}
                          </>
                        ) : (
                          <span className="text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-middle">
                        {profit != null ? (
                          <span className={clsx('flex items-center gap-1 font-semibold', profit >= 0 ? 'text-success' : 'text-danger')}>
                            {profit >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                            {formatMoney(profit)}
                          </span>
                        ) : (
                          <span className="text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-middle">
                        <div className="flex items-center gap-1.5">
                          {s.registry ? (
                            <span className={s.registry.is_active === false ? 'truncate text-danger' : 'truncate text-success'}>
                              {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
                            </span>
                          ) : (
                            <span className="text-ink-faint">—</span>
                          )}
                          {checko && (
                          <a
                            href={checko}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            title="Профиль на Checko"
                            className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-surface-hover"
                          >
                            <img src={checkoIcon} alt="Checko" className="h-3.5 w-3.5" />
                          </a>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 align-middle text-ink-soft">{s.total_requests}</td>
                      <td className="px-3 py-2.5 align-middle">
                        {s.total_requests > 0 ? (
                          <span className={s.response_rate >= 50 ? 'font-medium text-success' : 'text-ink-soft'}>{formatPercent(s.response_rate / 100)}</span>
                        ) : (
                          <span className="text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-middle text-ink-muted">{s.last_contact_at ? formatRelativeTime(s.last_contact_at) : 'Не было'}</td>
                      <td className="px-3 py-2.5 pr-6 align-middle">
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
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>
    </div>
  );
}
