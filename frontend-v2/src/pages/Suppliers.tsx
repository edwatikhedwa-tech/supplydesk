import clsx from 'clsx';
import { Ban, ExternalLink, FileSpreadsheet, Search, Star, TrendingDown, TrendingUp, Truck, Upload, X } from 'lucide-react';
import { useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { CopyButton } from '../components/ui/CopyButton';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { now, checkoUrl, companyAge, formatCompanyName, formatMoney, formatPercent, formatRelativeTime, pluralRu } from '../lib/format';
import type { SupplierDirectoryItem, SupplierImportApplyResult, SupplierImportPreview, SupplierImportTargetField } from '../lib/types';
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

const importFieldLabels: Record<SupplierImportTargetField, string> = {
  name: 'Название', inn: 'ИНН', site: 'Сайт', email: 'Email', phone: 'Телефон', region: 'Регион', role: 'Роль', note: 'Примечание',
};

const delimiterLabel = { comma: 'запятая', semicolon: 'точка с запятой', tab: 'tab' } as const;

function SupplierImportPanel({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [csvText, setCsvText] = useState('');
  const [fileName, setFileName] = useState('');
  const [preview, setPreview] = useState<SupplierImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, SupplierImportTargetField | null>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmationOpen, setConfirmationOpen] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<SupplierImportApplyResult | null>(null);

  const requestPreview = async (text: string, nextMapping?: Record<string, SupplierImportTargetField | null>) => {
    setBusy(true);
    setError('');
    try {
      const result = await api.previewSupplierImport({ csv_text: text, mapping: nextMapping });
      setPreview(result);
      setMapping(Object.fromEntries(result.columns.map((column) => [column.source, column.target])));
      setConfirmationOpen(false);
      setConfirmed(false);
      setResult(null);
    } catch (err) {
      setPreview(null);
      setError(err instanceof Error ? err.message : 'Не удалось разобрать CSV.');
    } finally {
      setBusy(false);
    }
  };

  const chooseFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 1_048_576) {
      setError('Файл больше 1 МБ. Уменьшите CSV для preview.');
      return;
    }
    setFileName(file.name);
    try {
      const text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
      setCsvText(text);
      await requestPreview(text);
    } catch {
      setPreview(null);
      setError('Поддерживается только CSV в кодировке UTF-8.');
    }
  };

  const updateMapping = async (source: string, target: string) => {
    if (!csvText) return;
    const nextMapping = { ...mapping, [source]: target ? target as SupplierImportTargetField : null };
    setMapping(nextMapping);
    await requestPreview(csvText, nextMapping);
  };

  const applyImport = async () => {
    if (!csvText || !confirmed) return;
    setBusy(true);
    setError('');
    try {
      const applied = await api.applySupplierImport({ csv_text: csvText, mapping, confirmed: true });
      setResult(applied);
      setConfirmationOpen(false);
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить поставщиков.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label="Предпросмотр импорта поставщиков" className="relative mx-4 mb-3 max-h-[calc(100dvh-7.5rem)] overflow-y-auto rounded-xl border border-accent-border bg-accent-subtle/35 p-4 pr-12 sm:mx-6 sm:max-h-none sm:overflow-visible">
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex min-w-0 gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white"><FileSpreadsheet size={16} /></span>
          <div className="min-w-0">
            <h2 className="font-medium text-ink">Импорт поставщиков</h2>
            <p className="mt-0.5 text-[12px] text-ink-muted">CSV в UTF‑8, до 1 МБ. Сначала проверка, затем только новые карточки после вашего подтверждения.</p>
          </div>
        </div>
      </div>
      <button type="button" onClick={onClose} aria-label="Закрыть импорт" className="absolute right-3 top-3 rounded-md p-1.5 text-ink-muted hover:bg-surface-hover hover:text-ink"><X size={16} /></button>

      <input ref={inputRef} type="file" accept=".csv,text/csv" className="sr-only" onChange={(event) => void chooseFile(event.target.files?.[0])} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => inputRef.current?.click()} disabled={busy} className="inline-flex h-8 items-center gap-1.5 rounded-md bg-accent px-3 text-[12.5px] font-medium text-white hover:bg-accent-hover disabled:cursor-wait disabled:opacity-70">
          <Upload size={14} /> {busy ? 'Разбираем…' : preview ? 'Выбрать другой CSV' : 'Выбрать CSV'}
        </button>
        {fileName && <span className="max-w-full truncate text-[12px] text-ink-muted">{fileName}</span>}
      </div>

      {error && <p role="alert" className="mt-3 rounded-md border border-danger/25 bg-danger-subtle px-3 py-2 text-[12px] text-danger">{error}</p>}
      {preview && (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap gap-2 text-[12px]">
            <Badge tone="neutral">{preview.summary.rows_total} строк</Badge>
            <Badge tone="success">К созданию: {preview.apply_plan.to_create}</Badge>
            {preview.summary.needs_attention > 0 && <Badge tone="warning">Проверить: {preview.summary.needs_attention}</Badge>}
            {preview.apply_plan.skipped_duplicates > 0 && <Badge tone="neutral">Дубликаты по ИНН: {preview.apply_plan.skipped_duplicates}</Badge>}
            <span className="self-center text-ink-muted">Разделитель: {delimiterLabel[preview.delimiter]} · запись: 0</span>
          </div>

          <div>
            <p className="mb-2 text-[12px] font-medium text-ink">Сопоставление столбцов</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {preview.columns.map((column) => (
                <label key={column.source} className="min-w-0 rounded-md border border-border bg-surface px-2 py-1.5 text-[11.5px] text-ink-muted">
                  <span className="block truncate" title={column.source}>{column.source}</span>
                  <select value={mapping[column.source] ?? ''} disabled={busy} onChange={(event) => void updateMapping(column.source, event.target.value)} className="mt-1 w-full bg-transparent text-[12px] font-medium text-ink outline-none disabled:opacity-60">
                    <option value="">Не импортировать</option>
                    {Object.entries(importFieldLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </label>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-border bg-surface">
            <table className="min-w-[620px] w-full text-left text-[11.5px]">
              <thead className="bg-canvas text-[10.5px] uppercase tracking-wide text-ink-muted"><tr><th className="px-3 py-2">Строка</th><th className="px-3 py-2">Поставщик</th><th className="px-3 py-2">ИНН</th><th className="px-3 py-2">Проверка</th></tr></thead>
              <tbody className="divide-y divide-border">
                {preview.rows.map((row) => <tr key={row.line}><td className="px-3 py-2 text-ink-muted">{row.line}</td><td className="max-w-56 truncate px-3 py-2 font-medium text-ink">{row.fields.name || '—'}</td><td className="px-3 py-2 text-ink-soft">{row.fields.inn || '—'}</td><td className="px-3 py-2 text-ink-muted">{row.issues.length ? row.issues.map((issue) => issue.message).join(' ') : 'Готово к следующему шагу'}</td></tr>)}
              </tbody>
            </table>
          </div>
          <div className="rounded-lg border border-border bg-surface px-3 py-3 text-[12px] text-ink-soft">
            <p>Будет создано: <strong className="font-medium text-ink">{preview.apply_plan.to_create}</strong>. Пропустим дубликаты по ИНН: <strong className="font-medium text-ink">{preview.apply_plan.skipped_duplicates}</strong>. Требуют исправления: <strong className="font-medium text-ink">{preview.apply_plan.skipped_attention}</strong>.</p>
            {preview.apply_plan.preview_only_fields.length > 0 && <p className="mt-1 text-ink-muted">Поля «{preview.apply_plan.preview_only_fields.map((field) => importFieldLabels[field]).join('», «')}» сейчас остаются только в preview и не будут сохранены.</p>}
            {!result && <button type="button" disabled={busy || preview.apply_plan.to_create === 0} onClick={() => { setConfirmationOpen(true); setConfirmed(false); }} className="mt-3 inline-flex h-8 items-center rounded-md border border-accent bg-surface px-3 text-[12.5px] font-medium text-accent hover:bg-accent-subtle disabled:cursor-not-allowed disabled:opacity-50">Проверить итог импорта</button>}
          </div>
          {confirmationOpen && <div role="dialog" aria-label="Подтверждение импорта" className="rounded-lg border border-accent-border bg-accent-subtle/45 p-3 text-[12px] text-ink-soft">
            <p className="font-medium text-ink">Подтвердите создание {preview.apply_plan.to_create} новых карточек</p>
            <p className="mt-1">Существующие поставщики не будут изменены. Совпадения по ИНН и строки с ошибками будут пропущены.</p>
            <label className="mt-3 flex cursor-pointer items-start gap-2 text-ink"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-0.5 h-3.5 w-3.5 accent-accent" />Я проверил итог и подтверждаю импорт.</label>
            <div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => { setConfirmationOpen(false); setConfirmed(false); }} disabled={busy} className="h-8 rounded-md border border-border-strong bg-surface px-3 text-[12px] font-medium text-ink-soft hover:bg-surface-hover">Отмена</button><button type="button" onClick={() => void applyImport()} disabled={!confirmed || busy} className="h-8 rounded-md bg-accent px-3 text-[12px] font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50">{busy ? 'Сохраняем…' : 'Создать карточки'}</button></div>
          </div>}
          {result && <div role="status" className="rounded-lg border border-success/30 bg-success-subtle px-3 py-3 text-[12px] text-ink-soft"><p className="font-medium text-ink">Импорт завершён</p><p className="mt-1">Создано: {result.created}. Пропущено дубликатов: {result.skipped_duplicates}. Не изменено существующих карточек: {result.updated}.</p></div>}
        </div>
      )}
    </section>
  );
}

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
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(() => searchParams.get('q') ?? '');
  const [filter, setFilter] = useState<FilterKey>('all');
  const [importOpen, setImportOpen] = useState(false);

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
            ? `${suppliers.length} ${pluralRu(suppliers.length, 'поставщик', 'поставщика', 'поставщиков')} · ${verifiedCount} с подтверждённым ИНН`
            : 'Загружаем поставщиков…'
        }
        actions={<button type="button" onClick={() => setImportOpen((open) => !open)} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border-strong bg-surface px-3 text-[12.5px] font-medium text-ink-soft hover:bg-surface-hover"><Upload size={14} /> Импорт CSV</button>}
      />

      {importOpen && <SupplierImportPanel onClose={() => setImportOpen(false)} onImported={state.reload} />}

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
                <col className="w-[23%]" />
                <col className="w-[7%]" />
                <col className="w-[11%]" />
                <col className="w-[11%]" />
                <col className="w-[12%]" />
                <col className="w-[7%]" />
                <col className="w-[7%]" />
                <col className="w-[10%]" />
                <col className="w-[12%]" />
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
                            <p className="whitespace-nowrap font-semibold text-ink">{formatMoney(s.finances.revenue)}</p>
                            {s.finances.report_year && <p className="text-[10.5px] text-ink-faint">за {s.finances.report_year}</p>}
                          </>
                        ) : (
                          <span className="text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-middle">
                        {profit != null ? (
                          <span className={clsx('flex whitespace-nowrap items-center gap-1 font-semibold', profit >= 0 ? 'text-success' : 'text-danger')}>
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
