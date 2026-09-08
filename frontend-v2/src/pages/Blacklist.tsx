import { AlertTriangle, Ban, Check, ExternalLink, Globe, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { PageHeader } from '../components/shell/PageHeader';
import { Button } from '../components/ui/Button';
import { CopyButton } from '../components/ui/CopyButton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { checkoUrl, companyAge, formatCompanyName, formatDateTime, formatMoney } from '../lib/format';
import type { BlacklistEntry, GlobalSupplierSummary } from '../lib/types';
import { useApiData } from '../lib/useApiData';

/** Two independent blacklists, shown on one screen (matches the legacy
 * frontend's Blacklist.tsx): global_suppliers rows with relationship_status
 * = 'blacklisted' (a company card exists), and blacklist_entries rows --
 * blocked marketplace/aggregator domains that were blocked before any
 * company card existed (mail/auth_accounts.py seeds e.g. Ozon on day one). */
export function Blacklist() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busyId, setBusyId] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const suppliersState = useApiData(() => api.listGlobalSuppliers().then((r) => r.items), []);
  const domainsState = useApiData(() => api.listBlacklist().then((r) => r.items), []);

  const suppliers = suppliersState.status === 'ready' ? suppliersState.data.filter((s) => s.relationship_status === 'blacklisted') : [];
  const domains = domainsState.status === 'ready' ? domainsState.data.filter((d) => !d.restored_at) : [];

  const filteredSuppliers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return suppliers;
    return suppliers.filter((s: GlobalSupplierSummary) => s.name.toLowerCase().includes(q) || s.inn.includes(q));
  }, [suppliers, search]);

  const filteredDomains = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return domains;
    return domains.filter((d: BlacklistEntry) => d.company_name.toLowerCase().includes(q) || d.external_key.toLowerCase().includes(q));
  }, [domains, search]);

  async function restoreSupplier(id: number) {
    setBusyId(id);
    try {
      await api.setGlobalSupplierRelationship(id, 'none');
      suppliersState.reload();
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } finally {
      setBusyId(null);
    }
  }

  async function restoreDomain(id: number) {
    setBusyId(id);
    try {
      await api.restoreBlacklist(id);
      domainsState.reload();
    } finally {
      setBusyId(null);
    }
  }

  async function restoreSelected() {
    setBulkBusy(true);
    try {
      await Promise.all([...selected].map((id) => api.setGlobalSupplierRelationship(id, 'none')));
      setSelected(new Set());
      suppliersState.reload();
    } finally {
      setBulkBusy(false);
    }
  }

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const loading = suppliersState.status === 'loading' || domainsState.status === 'loading';
  const error = suppliersState.status === 'error' ? suppliersState : domainsState.status === 'error' ? domainsState : null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader
        title="Чёрный список"
        description={loading ? 'Загружаем…' : `${suppliers.length} поставщиков · ${domains.length} доменов`}
      />

      <div className="mx-6 mb-3 flex items-start gap-2 rounded-md border border-warning-border bg-warning-subtle px-3 py-2 text-[12px] text-warning">
        <AlertTriangle size={14} className="mt-0.5 shrink-0" />
        Поставщики из чёрного списка не участвуют в автопоиске и недоступны для выбора при создании новой заявки.
      </div>

      <div className="flex items-center gap-3 px-6 pb-3">
        <div className="relative w-72">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Компания, ИНН или домен…"
            className="h-8 w-full rounded-md border border-border-strong bg-surface pl-8 pr-3 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 pb-6">
        {loading ? (
          <LoadingState label="Загружаем чёрный список…" />
        ) : error ? (
          <ErrorState message={error.message} onRetry={error.reload} />
        ) : (
          <div className="space-y-5">
            <section className="rounded-lg border border-border bg-surface">
              <h2 className="border-b border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink">Поставщики</h2>
              {filteredSuppliers.length === 0 ? (
                <EmptyState icon={Ban} title="В чёрном списке пусто" description="Здесь появятся поставщики, добавленные в чёрный список." />
              ) : (
                <table className="w-full table-fixed border-collapse text-[12.5px]">
                  <colgroup>
                    <col className="w-9" />
                    <col className="w-[22%]" />
                    <col className="w-[8%]" />
                    <col className="w-[11%]" />
                    <col className="w-[11%]" />
                    <col className="w-[10%]" />
                    <col className="w-[86px]" />
                    <col className="w-[19%]" />
                    <col className="w-[100px]" />
                  </colgroup>
                  <thead>
                    <tr className="border-b border-border">
                      {['', 'Компания', 'Возраст', 'Выручка', 'Прибыль', 'ЕГРЮЛ', '', 'Причина', 'В списке с'].map((h) => (
                        <th key={h} className="truncate px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted last:pr-6">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSuppliers.map((s) => {
                      const age = companyAge(s.registry?.registered_at);
                      const checko = checkoUrl(s.registry?.ogrn);
                      const profit = s.finances?.profit ?? null;
                      return (
                        <tr key={s.id} className="border-b border-border last:border-0 hover:bg-surface-hover">
                          <td className="px-3 py-2.5 pl-6 align-middle">
                            <input
                              type="checkbox"
                              checked={selected.has(s.id)}
                              onChange={() => toggleSelected(s.id)}
                              aria-label={`Выбрать ${s.name}`}
                              className="h-3.5 w-3.5 rounded border-border-strong accent-accent"
                            />
                          </td>
                          <td className="cursor-pointer px-3 py-2.5 align-middle" onClick={() => navigate(`/suppliers/${s.id}`)}>
                            <p className="truncate font-medium text-ink hover:text-accent">{formatCompanyName(s.name)}</p>
                            <p className="flex items-center gap-1 truncate text-[11px] text-ink-muted">
                              ИНН {s.inn}
                              {s.inn && <CopyButton text={s.inn} />}
                            </p>
                          </td>
                          <td className="px-3 py-2.5 align-middle text-ink-soft">{age ?? '—'}</td>
                          <td className="px-3 py-2.5 align-middle text-ink-soft">{s.finances?.revenue != null ? formatMoney(s.finances.revenue) : '—'}</td>
                          <td className={`px-3 py-2.5 align-middle ${profit != null ? (profit >= 0 ? 'text-success' : 'text-danger') : 'text-ink-faint'}`}>
                            {profit != null ? formatMoney(profit) : '—'}
                          </td>
                          <td className="px-3 py-2.5 align-middle">
                            {s.registry ? (
                              <span className={s.registry.is_active === false ? 'text-danger' : 'text-success'}>
                                {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
                              </span>
                            ) : (
                              <span className="text-ink-faint">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5 align-middle">
                            {checko && (
                              <a href={checko} target="_blank" rel="noreferrer" title="Профиль на Checko" className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-surface-hover">
                                <img src={checkoIcon} alt="Checko" className="h-3.5 w-3.5" />
                              </a>
                            )}
                          </td>
                          <td className="px-3 py-2.5 align-middle text-ink-soft">{s.blacklist_reason || '—'}</td>
                          <td className="px-3 py-2.5 pr-6 align-middle">
                            <div className="flex items-center justify-end gap-1.5">
                              <span className="text-[11px] text-ink-faint">{s.blacklisted_at ? formatDateTime(s.blacklisted_at) : '—'}</span>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 px-0"
                                icon={<Check size={13} />}
                                disabled={busyId === s.id}
                                onClick={() => void restoreSupplier(s.id)}
                                title="Вернуть из чёрного списка"
                                aria-label="Вернуть из чёрного списка"
                              />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </section>

            {filteredDomains.length > 0 && (
              <section className="rounded-lg border border-border bg-surface">
                <div className="border-b border-border px-4 py-2.5">
                  <h2 className="text-[12.5px] font-semibold text-ink">Домены</h2>
                  <p className="mt-0.5 text-[11.5px] text-ink-muted">
                    Агрегаторы и маркетплейсы, заблокированные до появления карточки компании — заявки не отправляются на эти домены.
                  </p>
                </div>
                <div className="divide-y divide-border">
                  {filteredDomains.map((d) => (
                    <div key={d.id} className="flex items-center gap-3 px-4 py-2.5">
                      <Globe size={14} className="shrink-0 text-ink-faint" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12.5px] font-medium text-ink">{d.company_name}</p>
                        <p className="truncate text-[11px] text-ink-faint">
                          {d.external_key}
                          {d.reason && <span> · {d.reason}</span>}
                        </p>
                      </div>
                      {d.host && (
                        <a
                          href={`https://${d.host}`}
                          target="_blank"
                          rel="noreferrer"
                          className="flex shrink-0 items-center gap-0.5 text-[11px] text-accent hover:underline"
                        >
                          {d.host} <ExternalLink size={9} />
                        </a>
                      )}
                      <Button variant="ghost" size="sm" icon={<Check size={13} />} disabled={busyId === d.id} onClick={() => void restoreDomain(d.id)}>
                        Вернуть
                      </Button>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>

      {selected.size > 0 && (
        <div className="flex items-center justify-between border-t border-border bg-surface px-6 py-3 shadow-lg">
          <span className="text-[12.5px] text-ink-soft">
            Выбрано: <b>{selected.size}</b>
          </span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
              Снять выбор
            </Button>
            <Button variant="primary" size="sm" icon={<Check size={13} />} disabled={bulkBusy} onClick={() => void restoreSelected()}>
              {bulkBusy ? 'Возвращаем…' : 'Вернуть выбранных'}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
