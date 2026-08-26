import { useEffect, useState } from 'react';
import { Check, ExternalLink, PackageSearch, RotateCcw } from 'lucide-react';
import { displaySupplierName, formatFullDate, formatRelativeDate } from '@/lib/utils';
import { RelationshipBadge, issueReasonLabels } from './StatusBits';
import { AgeCell, CheckoLinkCell, ProfitCell, RegistryStatusCell, RevenueCell } from './RegistryFinanceRow';
import type { GlobalSupplierSummary } from '@/lib/types';

export type GlobalSupplierTableView = 'all' | 'blacklist';

interface GlobalSupplierTableProps {
  view: GlobalSupplierTableView;
  suppliers: GlobalSupplierSummary[];
  loading: boolean;
  emptyMessage: string;
  selected: Set<number>;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: () => void;
  onOpenSupplier: (id: number) => void;
  onRestore?: (id: number) => void;
}

const PAGE_SIZE = 50;

/** One column definition shared by the header and every row — see the same
 * helper in components/SupplierTable.tsx. Fixed widths for the short,
 * predictable registry facts; minmax() only where content really varies. */
function gridTemplate(view: GlobalSupplierTableView): string {
  const common = ['44px', 'minmax(200px,1.3fr)', 'minmax(150px,0.9fr)'];
  return (view === 'all'
    ? [...common, '74px', '104px', '104px', '104px', '44px', '68px', '78px', 'minmax(120px,0.8fr)', 'minmax(110px,0.7fr)']
    //  checkbox, Название, Специализация, Возраст, Выручка, Прибыль, ЕГРЮЛ, Checko, Заявок, Отклик, Последний контакт, Статус
    : [...common, '74px', '104px', '104px', '104px', '44px', 'minmax(140px,1fr)', 'minmax(120px,0.8fr)', '110px']
    //  checkbox, Название, Специализация, Возраст, Выручка, Прибыль, ЕГРЮЛ, Checko, Причина, В списке с, действие
  ).join(' ');
}

export function GlobalSupplierTable({
  view, suppliers, loading, emptyMessage, selected,
  onToggleSelect, onToggleSelectAll, onOpenSupplier, onRestore,
}: GlobalSupplierTableProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  // A new filter/search narrows the list — always start back at the top of it,
  // otherwise "Показать ещё" state from a longer previous list would just hide
  // rows that now fit within the first page.
  useEffect(() => setVisibleCount(PAGE_SIZE), [suppliers]);
  const visibleSuppliers = suppliers.slice(0, visibleCount);
  const template = gridTemplate(view);
  const minWidth = view === 'all' ? 1250 : 1110;

  const allSelected = suppliers.length > 0 && suppliers.every((s) => selected.has(s.id));
  const someSelected = suppliers.some((s) => selected.has(s.id));

  return (
    <div className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-soft">
      <div className="overflow-x-auto">
        <div style={{ minWidth }}>
          <div
            className="grid items-center gap-3 border-b border-ink-200 bg-ink-50 px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-ink-600"
            style={{ gridTemplateColumns: template }}
          >
            <div className="flex items-center justify-center">
              <button onClick={onToggleSelectAll} className="flex h-9 w-9 items-center justify-center" aria-label="Выбрать всех">
                <span className={`flex h-5 w-5 items-center justify-center rounded border-2 transition-colors ${
                  allSelected ? 'border-accent-600 bg-accent-600' : someSelected ? 'border-accent-400 bg-accent-400' : 'border-ink-300 hover:border-accent-400'
                }`}>
                  {(allSelected || someSelected) && <Check className="h-3 w-3 text-white" />}
                </span>
              </button>
            </div>
            <div>Название</div>
            <div>Специализация</div>
            <div>Возраст</div>
            <div>Выручка</div>
            <div>Прибыль</div>
            <div>ЕГРЮЛ</div>
            <div className="text-center" title="Профиль компании на Checko">Checko</div>
            {view === 'all' ? (
              <>
                <div className="text-center">Заявок</div>
                <div className="text-center">Отклик</div>
                <div>Последний контакт</div>
                <div>Статус</div>
              </>
            ) : (
              <>
                <div>Причина</div>
                <div>В списке с</div>
                <div />
              </>
            )}
          </div>

          <div className="divide-y divide-ink-100">
            {loading ? (
              <div className="px-5 py-12 text-center text-sm text-ink-400">Загрузка…</div>
            ) : suppliers.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-5 py-16 text-center">
                <PackageSearch className="h-8 w-8 text-ink-300" />
                <p className="text-sm text-ink-400">{emptyMessage}</p>
              </div>
            ) : (
              visibleSuppliers.map((s) => {
                const isSelected = selected.has(s.id);
                return (
                  <div
                    key={s.id}
                    onClick={() => onOpenSupplier(s.id)}
                    className={`group grid cursor-pointer items-center gap-3 px-5 py-3 transition-colors ${isSelected ? 'bg-accent-50' : 'hover:bg-ink-50'}`}
                    style={{ gridTemplateColumns: template }}
                  >
                    <div className="flex items-center justify-center" onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => onToggleSelect(s.id)} className="flex h-9 w-9 items-center justify-center" aria-label="Выбрать поставщика">
                        <span className={`flex h-5 w-5 items-center justify-center rounded border-2 transition-colors ${isSelected ? 'border-accent-600 bg-accent-600' : 'border-ink-300 hover:border-accent-400'}`}>
                          {isSelected && <Check className="h-3 w-3 text-white" />}
                        </span>
                      </button>
                    </div>

                    <div className="min-w-0">
                      <div title={s.name || undefined} className="truncate text-sm font-medium text-ink-800 transition-colors group-hover:text-accent-700">{s.name ? displaySupplierName(s.name, s.inn) : s.site}</div>
                      <div className="flex min-w-0 items-center gap-1.5 truncate text-xs text-ink-400">
                        <span className="shrink-0">ИНН {s.inn}</span>
                        {s.site && (
                          <>
                            <span className="shrink-0 text-ink-300">·</span>
                            <a
                              href={`https://${s.site}`}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              title={`Открыть ${s.site} в новой вкладке`}
                              className="inline-flex min-w-0 items-center gap-0.5 truncate hover:text-accent-600 hover:underline"
                            >
                              <ExternalLink className="h-2.5 w-2.5 shrink-0" />{s.site}
                            </a>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex min-w-0 flex-wrap gap-1">
                      {s.categories.slice(0, 2).map((cat) => (
                        <span key={cat} className="truncate rounded-md bg-ink-100 px-2 py-0.5 text-[11px] font-medium text-ink-600">{cat}</span>
                      ))}
                      {s.categories.length > 2 && <span className="px-1.5 py-0.5 text-[11px] text-ink-400">+{s.categories.length - 2}</span>}
                      {s.categories.length === 0 && <span className="text-xs text-ink-300">—</span>}
                    </div>

                    <div><AgeCell registry={s.registry} /></div>
                    <div><RevenueCell finances={s.finances} /></div>
                    <div><ProfitCell finances={s.finances} /></div>
                    <div className="min-w-0"><RegistryStatusCell registry={s.registry} /></div>
                    <div className="flex justify-center" onClick={(e) => e.stopPropagation()}><CheckoLinkCell registry={s.registry} /></div>

                    {view === 'all' ? (
                      <>
                        <div className="text-center text-sm tabular-nums text-ink-700">{s.total_requests}</div>
                        <div className="text-center">
                          {s.total_requests === 0 ? (
                            <span className="text-sm text-ink-300">—</span>
                          ) : (
                            <>
                              <div className="whitespace-nowrap text-sm font-medium tabular-nums text-ink-700">{s.response_rate}%</div>
                              {s.response_rate === 0 && <div className="whitespace-nowrap text-[10px] text-ink-400">ждём</div>}
                            </>
                          )}
                        </div>
                        <div className="truncate text-xs text-ink-500">{formatRelativeDate(s.last_contact_at)}</div>
                        <div className="min-w-0"><RelationshipBadge status={s.relationship_status} /></div>
                      </>
                    ) : (
                      <>
                        <div className="min-w-0 truncate text-xs text-ink-600" title={s.blacklist_reason || undefined}>
                          {s.blacklist_reason ? issueReasonLabels[s.blacklist_reason] || s.blacklist_reason : '—'}
                        </div>
                        <div className="truncate text-xs text-ink-500">{s.blacklisted_at ? formatFullDate(s.blacklisted_at) : '—'}</div>
                        <div className="text-right" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => onRestore?.(s.id)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-ink-200 px-2.5 py-1.5 text-xs font-semibold text-ink-600 hover:border-ink-300 hover:text-ink-900"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />Вернуть
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>

          {visibleCount < suppliers.length && (
            <div className="flex justify-center border-t border-ink-100 py-3">
              <button
                onClick={() => setVisibleCount((v) => v + PAGE_SIZE)}
                className="rounded-lg px-4 py-2 text-xs font-semibold text-accent-600 hover:bg-accent-50"
              >
                Показать ещё ({suppliers.length - visibleCount})
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
