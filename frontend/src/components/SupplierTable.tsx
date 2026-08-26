import { useEffect, useState, type MouseEvent } from 'react';
import { ArrowRight, Check, ExternalLink, Mail, MapPin, MessageSquare, PackageSearch, Phone } from 'lucide-react';
import type { Supplier } from '@/lib/types';
import { STATUS_META } from '@/useRequestState';
import { displaySupplierName } from '@/lib/utils';
import {
  AgeCell, CheckoLinkCell, ProfitCell, RegistryStatusCell, RevenueCell,
} from '@/components/suppliers/RegistryFinanceRow';
import { RoleBadge } from '@/components/suppliers/StatusBits';

const PAGE_SIZE = 50;

interface Props {
  suppliers: Supplier[];
  itemNames: (supplier: Supplier) => string[];
  /** Positions on the заявка itself (not per-row) — a single-position request
   * would otherwise repeat the same tag on every one of dozens of rows, and an
   * always-present column would waste the width. */
  totalPositions: number;
  selectedIds: Set<number>;
  recentlyChanged: Set<number>;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: (ids: number[]) => void;
  onOpenSupplier: (id: number) => void;
  onWriteSupplier: (id: number) => void;
}

const ITEM_TAGS_LIMIT = 2;

/** One column definition shared by the header and every row, so the two can
 * never drift apart. Fixed widths for the short, predictable facts (age,
 * revenue, ЕГРЮЛ, Checko link) and `minmax(...)` only for the columns whose
 * content genuinely varies — that's what stops a short name from leaving a
 * gap the width of the screen before the next column. */
function gridTemplate(hasPositions: boolean): string {
  return [
    '44px',                 // checkbox
    'minmax(190px,1.25fr)', // Название
    'minmax(165px,1fr)',    // Контакты
    hasPositions ? 'minmax(110px,0.7fr)' : null, // Позиции
    '74px',                 // Возраст
    '104px',                // Выручка
    '104px',                // Прибыль
    '104px',                // ЕГРЮЛ
    '44px',                 // Checko
    '116px',                // Статус письма
    '76px',                 // действия
  ].filter(Boolean).join(' ');
}

/** Opens the supplier's own site straight from the row — stopPropagation keeps
 * the row's own click (which opens the detail panel) from firing too. */
function SiteLink({ host }: { host: string }) {
  if (!host) return null;
  return (
    <a
      href={`https://${host}`}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
      title={`Открыть ${host} в новой вкладке`}
      className="inline-flex min-w-0 items-center gap-0.5 truncate hover:text-accent-600 hover:underline"
    >
      <ExternalLink className="h-2.5 w-2.5 shrink-0" />{host}
    </a>
  );
}

function RowCheckbox({ checked, disabled, onClick }: { checked: boolean; disabled?: boolean; onClick: (e: MouseEvent<HTMLButtonElement>) => void }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={onClick}
      className="flex h-9 w-9 items-center justify-center"
    >
      <span
        className={[
          'flex h-5 w-5 items-center justify-center rounded border-2 transition-colors',
          disabled
            ? 'border-ink-200 bg-ink-100'
            : checked
              ? 'border-accent-600 bg-accent-600'
              : 'border-ink-300 bg-white hover:border-accent-400',
        ].join(' ')}
      >
        {checked && !disabled && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
      </span>
    </button>
  );
}

export function SupplierTable({ suppliers, itemNames, totalPositions, selectedIds, onToggleSelect, onToggleSelectAll, onOpenSupplier, onWriteSupplier }: Props) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  useEffect(() => setVisibleCount(PAGE_SIZE), [suppliers]);
  const visibleSuppliers = suppliers.slice(0, visibleCount);
  const hasPositions = totalPositions > 1;
  const template = gridTemplate(hasPositions);

  const eligibleIds = suppliers.filter((s) => s.email).map((s) => s.id);
  const allSelected = eligibleIds.length > 0 && eligibleIds.every((id) => selectedIds.has(id));
  const someSelected = eligibleIds.some((id) => selectedIds.has(id));

  return (
    <div className="mx-6 overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-soft lg:mx-10">
      <div className="overflow-x-auto">
        <div className="min-w-[1050px]">
          <div
            className="grid items-center gap-3 border-b border-ink-200 bg-ink-50 px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-ink-600"
            style={{ gridTemplateColumns: template }}
          >
            <div className="flex items-center justify-center">
              <button onClick={() => onToggleSelectAll(eligibleIds)} className="flex h-9 w-9 items-center justify-center" aria-label="Выбрать всех с email">
                <span className={`flex h-5 w-5 items-center justify-center rounded border-2 transition-colors ${
                  allSelected ? 'border-accent-600 bg-accent-600' : someSelected ? 'border-accent-400 bg-accent-400' : 'border-ink-300 hover:border-accent-400'
                }`}>
                  {(allSelected || someSelected) && <Check className="h-3 w-3 text-white" />}
                </span>
              </button>
            </div>
            <div>Название</div>
            <div>Контакты</div>
            {hasPositions && <div>Позиции</div>}
            <div>Возраст</div>
            <div>Выручка</div>
            <div>Прибыль</div>
            <div>ЕГРЮЛ</div>
            <div className="text-center" title="Профиль компании на Checko">Checko</div>
            <div>Статус</div>
            <div />
          </div>

          {suppliers.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-5 py-16 text-center">
              <PackageSearch className="h-8 w-8 text-ink-300" />
              <p className="text-sm text-ink-400">Поставщики не найдены.</p>
            </div>
          ) : (
            <div className="divide-y divide-ink-100">
              {visibleSuppliers.map((s) => {
                const meta = STATUS_META[s.mail_status];
                const items = itemNames(s);
                const visibleItems = items.slice(0, ITEM_TAGS_LIMIT);
                const extraItems = items.length - visibleItems.length;
                const disabled = !s.email;
                const canOpenResponse = s.mail_status === 'answered';
                const isSelected = selectedIds.has(s.id);

                return (
                  <div
                    key={s.id}
                    onClick={() => onOpenSupplier(s.id)}
                    className={`group grid cursor-pointer items-center gap-3 px-5 py-3 transition-colors ${isSelected ? 'bg-accent-50' : 'hover:bg-ink-50'}`}
                    style={{ gridTemplateColumns: template }}
                  >
                    <div className="flex items-center justify-center" onClick={(e) => e.stopPropagation()}>
                      <RowCheckbox checked={isSelected} disabled={disabled} onClick={() => onToggleSelect(s.id)} />
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {/* An ИНН means the name went through registry/crawl confirmation; without
                            one, `name` is often just the raw SERP page title (see C-07) — lead
                            with the domain instead, since that's always real. */}
                        {/* Only a confirmed registry record proves `name` is a real
                            company name. An ИНН alone doesn't: it can belong to a
                            marketplace whose page we crawled (am.ozon.com carries
                            Ozon's ИНН), and then `name` is still the raw SERP page
                            title — "Поверхностный насос LEO AMSm120/1.1…". Without
                            that proof the domain is the honest label. */}
                        <span title={s.name} className="truncate text-sm font-semibold text-ink-800">
                          {s.registry ? displaySupplierName(s.name, s.inn) : s.host}
                        </span>
                        <RoleBadge role={s.role} />
                        {s.email && <span className="hidden shrink-0 whitespace-nowrap rounded-full bg-emerald-50 px-1.5 py-px text-2xs font-semibold text-emerald-600 ring-1 ring-emerald-200/70 sm:inline">Email ✓</span>}
                      </div>
                      <div className="mt-0.5 flex min-w-0 items-center gap-1.5 truncate text-2xs text-ink-400">
                        {s.inn && <><span className="shrink-0">ИНН {s.inn}</span><span className="shrink-0 text-ink-300">·</span></>}
                        <SiteLink host={s.host} />
                      </div>
                    </div>

                    <div className="min-w-0">
                      {s.email ? (
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5 truncate text-xs text-ink-600">
                            <Mail className="h-3 w-3 shrink-0 text-ink-400" /><span className="truncate">{s.email}</span>
                          </div>
                          <div className="flex items-center gap-2 text-2xs text-ink-400">
                            {s.phone && <span className="inline-flex items-center gap-1"><Phone className="h-3 w-3 shrink-0" />{s.phone}</span>}
                            {s.region && <span className="inline-flex min-w-0 items-center gap-1 truncate"><MapPin className="h-3 w-3 shrink-0" />{s.region}</span>}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-0.5">
                          <span className="text-xs text-ink-400">Нет email</span>
                          {s.region && (
                            <div className="flex items-center gap-1 text-2xs text-ink-400"><MapPin className="h-3 w-3 shrink-0" />{s.region}</div>
                          )}
                        </div>
                      )}
                    </div>

                    {hasPositions && (
                      <div className="flex min-w-0 flex-wrap items-center gap-1">
                        {visibleItems.map((item) => (
                          <span key={item} className="truncate rounded-md bg-ink-100/80 px-1.5 py-0.5 text-2xs font-medium text-ink-600">{item}</span>
                        ))}
                        {extraItems > 0 && <span className="rounded-md bg-ink-200/70 px-1.5 py-0.5 text-2xs font-medium text-ink-500">+{extraItems}</span>}
                      </div>
                    )}

                    <div><AgeCell registry={s.registry} /></div>
                    <div><RevenueCell finances={s.finances} /></div>
                    <div><ProfitCell finances={s.finances} /></div>
                    <div className="min-w-0"><RegistryStatusCell registry={s.registry} /></div>
                    <div className="flex justify-center" onClick={(e) => e.stopPropagation()}><CheckoLinkCell registry={s.registry} /></div>

                    <div className="min-w-0">
                      {s.mail_status === 'not_sent' ? (
                        <span className="text-2xs text-ink-400">{meta.label}</span>
                      ) : (
                        <span className={`inline-flex w-fit items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-2xs font-semibold ring-1 ${meta.badge} ${s.mail_status === 'answered' ? 'shadow-sm' : ''}`}>
                          <span className={meta.dot}>{meta.icon}</span>{meta.label}
                        </span>
                      )}
                      {s.mail_status === 'error' && s.last_error && (
                        <span className="mt-0.5 block truncate text-2xs text-rose-400" title={s.last_error}>{s.last_error}</span>
                      )}
                    </div>

                    <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      {canOpenResponse && (
                        <button
                          onClick={(e) => { e.stopPropagation(); onOpenSupplier(s.id); }}
                          className="rounded-md bg-emerald-50 px-2 py-1 text-2xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-100"
                        >
                          Открыть
                        </button>
                      )}
                      <button
                        title="Написать"
                        onClick={(e) => { e.stopPropagation(); onWriteSupplier(s.id); }}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-700"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                      </button>
                      <button
                        title="Открыть"
                        onClick={(e) => { e.stopPropagation(); onOpenSupplier(s.id); }}
                        className="flex h-7 w-7 items-center justify-center rounded-md text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-700"
                      >
                        <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

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
