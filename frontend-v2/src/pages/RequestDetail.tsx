import { ArrowLeft, Ban, ExternalLink, Inbox, MessageSquareText, Package, PenSquare, RotateCw, Search, Send } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { BulkComposeModal } from '../components/BulkComposeModal';
import { QuickAddTaskButton } from '../components/QuickAddTaskButton';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { CopyButton } from '../components/ui/CopyButton';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { checkoUrl, companyAge, formatCompanyName, formatMoney } from '../lib/format';
import { requestStatusMeta, supplierMailStatusMeta } from '../lib/statusMeta';
import type { RequestSupplierRow, SupplierSendInput } from '../lib/types';
import { useApiData } from '../lib/useApiData';

function toSendInput(s: RequestSupplierRow): SupplierSendInput {
  return { id: s.id, email: s.email, name: s.name, host: s.host, external_key: s.external_key, inn: s.inn, global_supplier_id: s.global_supplier_id };
}

type FilterKey = 'all' | 'has_contact' | 'no_contact' | 'sent' | 'waiting' | 'answered' | 'error' | 'delivery_unknown';

const FILTER_LABELS: Record<FilterKey, string> = {
  all: 'Все',
  has_contact: 'С контактами',
  no_contact: 'Без контакта',
  sent: 'Отправлено',
  waiting: 'Ждём ответа',
  answered: 'Получен ответ',
  error: 'Ошибка отправки',
  delivery_unknown: 'Статус неизвестен',
};

function matchesFilter(s: RequestSupplierRow, filter: FilterKey): boolean {
  switch (filter) {
    case 'all':
      return true;
    case 'has_contact':
      return s.email_count > 0;
    case 'no_contact':
      return s.email_count === 0;
    default:
      return s.mail_status === filter;
  }
}

export function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const requestId = Number(id);
  const navigate = useNavigate();
  const state = useApiData(() => api.getRequestDetail(requestId), [requestId]);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const [irrelevantId, setIrrelevantId] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [composeOpen, setComposeOpen] = useState(false);
  const [quickComposeId, setQuickComposeId] = useState<number | null>(null);

  const suppliers = state.status === 'ready' ? state.data.items : [];

  const counts = useMemo(() => {
    const c: Record<FilterKey, number> = {
      all: suppliers.length,
      has_contact: 0,
      no_contact: 0,
      sent: 0,
      waiting: 0,
      answered: 0,
      error: 0,
      delivery_unknown: 0,
    };
    for (const s of suppliers) {
      if (s.email_count > 0) c.has_contact++;
      else c.no_contact++;
      if (s.mail_status in c) c[s.mail_status as FilterKey]++;
    }
    return c;
  }, [suppliers]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return suppliers.filter((s) => {
      if (!matchesFilter(s, filter)) return false;
      if (!q) return true;
      const haystack = `${s.name} ${s.host} ${s.email} ${s.inn}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [suppliers, filter, query]);

  if (!id || Number.isNaN(requestId)) {
    return <EmptyState icon={Ban} title="Некорректный номер заявки" />;
  }
  if (state.status === 'loading') {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <PageHeader title="Заявка" />
        <LoadingState label="Загружаем заявку…" />
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <PageHeader title="Заявка" />
        <ErrorState message={state.message} onRetry={state.reload} />
      </div>
    );
  }

  const { request, positions } = state.data;
  const statusMeta = requestStatusMeta[request.status];
  const metrics = request.mail_metrics;

  async function retrySearch() {
    setRetrying(true);
    setRetryError('');
    try {
      await api.startRequestSearch(requestId);
      state.reload();
    } catch (e) {
      setRetryError(e instanceof ApiError ? e.message : 'Не удалось перезапустить поиск.');
    } finally {
      setRetrying(false);
    }
  }

  async function markIrrelevant(supplierId: number) {
    setIrrelevantId(supplierId);
    try {
      await api.markSupplierIrrelevant(requestId, supplierId);
      state.reload();
    } catch {
      // Silently keep the row -- the button staying enabled is feedback enough for a soft-fail here.
    } finally {
      setIrrelevantId(null);
    }
  }

  function openThread(supplierId: number) {
    navigate(`/messages?request=${requestId}&supplier=${supplierId}`);
  }

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setSelected((prev) => (visible.every((s) => prev.has(s.id)) ? new Set() : new Set(visible.map((s) => s.id))));
  }

  const selectedSuppliers = suppliers.filter((s) => selected.has(s.id) && s.email);
  const quickComposeSupplier = quickComposeId != null ? (suppliers.find((s) => s.id === quickComposeId) ?? null) : null;
  const composeRecipients = quickComposeSupplier ? [quickComposeSupplier] : selectedSuppliers;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 px-4 sm:px-6 pt-5">
        <Link to="/requests" className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink">
          <ArrowLeft size={13} />
          Заявки
        </Link>
      </div>

      <PageHeader
        title={request.name}
        description={`№${request.id} · ${request.sender_name}${request.company_name ? ` · ${request.company_name}` : ''}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
            <DeadlineTag deadline={request.deadline} />
            <QuickAddTaskButton requestId={requestId} />
            {(request.status === 'error' || request.status === 'completed') && (
              <Button variant="secondary" size="sm" icon={<RotateCw size={13} />} disabled={retrying} onClick={() => void retrySearch()}>
                {retrying ? 'Запускаем…' : 'Перезапустить поиск'}
              </Button>
            )}
          </div>
        }
      />

      {retryError && <p className="px-4 sm:px-6 pb-2 text-[12px] text-danger">{retryError}</p>}

      {request.description && <p className="px-4 sm:px-6 pb-3 text-[12.5px] text-ink-soft">{request.description}</p>}

      {positions.length > 0 && (
        <div className="px-4 sm:px-6 pb-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">
            <Package size={12} />
            Позиции заявки
          </div>
          <div className="flex flex-wrap gap-1.5">
            {positions.map((p) => (
              <span key={p.position_key} className="rounded-md border border-border-strong bg-surface px-2.5 py-1 text-[12px] text-ink-soft">
                {p.name}
                {p.quantity ? <span className="text-ink-faint"> · {p.quantity}</span> : null}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border px-4 sm:px-6 py-2.5 text-[11.5px] text-ink-muted">
        <span>
          <b className="text-ink">{suppliers.length}</b> компаний
        </span>
        <span>
          <b className="text-ink">{counts.has_contact}</b> с контактами
        </span>
        <span>
          <b className="text-warning">{counts.waiting}</b> ждут ответа
        </span>
        <span>
          <b className="text-success">{counts.answered}</b> с ответом
        </span>
        {metrics && (
          <span className="text-ink-faint">
            Письма: {metrics.accepted_effective} отправлено
            {metrics.failed > 0 && <span className="text-danger"> · {metrics.failed} ошибок</span>}
            {metrics.bounced > 0 && <span className="text-danger"> · {metrics.bounced} не доставлено</span>}
            {metrics.delivery_unknown > 0 && <span> · {metrics.delivery_unknown} статус неизвестен</span>}
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 sm:px-6 py-2.5">
        <div className="flex flex-wrap gap-1.5">
          {(Object.keys(FILTER_LABELS) as FilterKey[])
            .filter((key) => key === 'all' || counts[key] > 0)
            .map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                className={
                  filter === key
                    ? 'rounded-md bg-accent px-2.5 py-1 text-[11.5px] font-medium text-white'
                    : 'rounded-md border border-border-strong px-2.5 py-1 text-[11.5px] text-ink-soft hover:bg-surface-hover'
                }
              >
                {FILTER_LABELS[key]} <span className="tabular-nums opacity-70">{counts[key]}</span>
              </button>
            ))}
        </div>
        {selectedSuppliers.length > 0 && (
          <Button variant="primary" size="sm" icon={<PenSquare size={13} />} onClick={() => setComposeOpen(true)}>
            Написать ({selectedSuppliers.length})
          </Button>
        )}
        <div className="relative ml-auto w-[240px]">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск: компания, сайт, ИНН…"
            className="h-8 w-full rounded-md border border-border-strong bg-surface pl-7 pr-2.5 text-[12px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>
      </div>

      {(composeOpen || quickComposeSupplier) && (
        <BulkComposeModal
          requestId={requestId}
          recipients={composeRecipients.map(toSendInput)}
          onClose={() => {
            setComposeOpen(false);
            setQuickComposeId(null);
          }}
          onSent={() => {
            setSelected(new Set());
            setQuickComposeId(null);
            state.reload();
          }}
        />
      )}

      <div className="min-w-0 flex-1 overflow-auto border-t border-border">
        {suppliers.length === 0 ? (
          <EmptyState icon={Inbox} title="Поставщики ещё не найдены" description="Запустите поиск, чтобы система нашла кандидатов." />
        ) : visible.length === 0 ? (
          <EmptyState icon={Search} title="Ничего не найдено" description="Попробуйте другой фильтр или запрос." />
        ) : (
          <>
          <div className="flex flex-col divide-y divide-border sm:hidden">
            {visible.map((s) => {
              const mailMeta = supplierMailStatusMeta[s.mail_status] ?? supplierMailStatusMeta.not_sent;
              const age = companyAge(s.registry?.registered_at);
              const checko = checkoUrl(s.registry?.ogrn);
              return (
                <div key={s.id} className={`flex flex-col gap-2 px-4 py-3 ${selected.has(s.id) ? 'bg-accent-subtle/30' : ''}`}>
                  <div className="flex items-start gap-2.5">
                    <input
                      type="checkbox"
                      checked={selected.has(s.id)}
                      onChange={() => toggleSelected(s.id)}
                      disabled={!s.email}
                      aria-label={`Выбрать ${s.name}`}
                      className="mt-1 h-3.5 w-3.5 shrink-0 rounded border-border-strong accent-accent disabled:opacity-30"
                    />
                    <div className="min-w-0 flex-1">
                      {s.global_supplier_id ? (
                        <Link to={`/suppliers/${s.global_supplier_id}`} className="truncate font-medium text-ink hover:text-accent">
                          {formatCompanyName(s.name)}
                        </Link>
                      ) : (
                        <p className="truncate font-medium text-ink">{formatCompanyName(s.name)}</p>
                      )}
                      <p className="truncate text-[11px] text-ink-muted">
                        {s.email || 'Нет email'}
                        {s.inn && <span> · ИНН {s.inn}</span>}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px]">
                        {age && <span className="text-ink-faint">{age}</span>}
                        {s.finances && <span className="text-ink-soft">{formatMoney(s.finances.revenue)}</span>}
                        <Badge tone={mailMeta.tone}>{mailMeta.label}</Badge>
                        {s.unread_count > 0 && (
                          <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                            {s.unread_count}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-1.5">
                    {checko && (
                      <a href={checko} target="_blank" rel="noreferrer" title="Профиль на Checko" className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-surface-hover">
                        <img src={checkoIcon} alt="Checko" className="h-4 w-4" />
                      </a>
                    )}
                    {s.email && (
                      <button type="button" onClick={() => setQuickComposeId(s.id)} title="Написать" aria-label="Написать"
                        className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-subtle text-accent transition-colors hover:bg-accent hover:text-white">
                        <Send size={13} />
                      </button>
                    )}
                    <button type="button" onClick={() => openThread(s.id)} title="Переписка" aria-label="Переписка"
                      className="flex h-7 w-7 items-center justify-center rounded-full bg-info-subtle text-info transition-colors hover:bg-info hover:text-white">
                      <MessageSquareText size={13} />
                    </button>
                    <button type="button" disabled={irrelevantId === s.id} onClick={() => void markIrrelevant(s.id)}
                      title="Не подходит" aria-label="Не подходит"
                      className="flex h-7 w-7 items-center justify-center rounded-full bg-danger-subtle text-danger transition-colors hover:bg-danger hover:text-white disabled:opacity-50">
                      <Ban size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full table-fixed border-collapse text-[12.5px]">
              <colgroup>
                <col className="w-9" />
                <col className="w-[19%]" />
                <col className="w-[16%]" />
                <col className="w-[6%]" />
                <col className="w-[8%]" />
                <col className="w-[8%]" />
                <col className="w-[8%]" />
                <col className="w-[11%]" />
                <col className="w-[148px]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-canvas">
                <tr className="border-b border-border">
                  <th className="px-3 py-2 pl-6">
                    <input
                      type="checkbox"
                      checked={visible.length > 0 && visible.every((s) => selected.has(s.id))}
                      onChange={toggleSelectAllVisible}
                      aria-label="Выбрать всех"
                      className="h-3.5 w-3.5 rounded border-border-strong accent-accent"
                    />
                  </th>
                  {['Компания', 'Контакты', 'Возраст', 'Выручка', 'Прибыль', 'ЕГРЮЛ', 'Статус письма', ''].map((h) => (
                    <th key={h} className="truncate px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted last:pr-6">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((s) => {
                  const mailMeta = supplierMailStatusMeta[s.mail_status] ?? supplierMailStatusMeta.not_sent;
                  const age = companyAge(s.registry?.registered_at);
                  const checko = checkoUrl(s.registry?.ogrn);
                  const site = s.host ? (s.host.startsWith('http') ? s.host : `https://${s.host}`) : null;
                  return (
                    <tr key={s.id} className={`border-b border-border last:border-0 hover:bg-surface-hover ${selected.has(s.id) ? 'bg-accent-subtle/30' : ''}`}>
                      <td className="px-3 py-2.5 pl-6 align-top">
                        <input
                          type="checkbox"
                          checked={selected.has(s.id)}
                          onChange={() => toggleSelected(s.id)}
                          disabled={!s.email}
                          title={s.email ? undefined : 'Нет email — нельзя выбрать для рассылки'}
                          aria-label={`Выбрать ${s.name}`}
                          className="h-3.5 w-3.5 rounded border-border-strong accent-accent disabled:opacity-30"
                        />
                      </td>
                      <td className="px-3 py-2.5 align-top">
                        <div className="min-w-0">
                          {s.global_supplier_id ? (
                            <Link
                              to={`/suppliers/${s.global_supplier_id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="truncate font-medium text-ink hover:text-accent hover:underline"
                            >
                              {formatCompanyName(s.name)}
                            </Link>
                          ) : (
                            <p className="truncate font-medium text-ink" title="Карточка появится после подтверждения ИНН">
                              {formatCompanyName(s.name)}
                            </p>
                          )}
                          <p className="truncate text-[11px] text-ink-muted">
                            {s.inn && <span>ИНН {s.inn}</span>}
                            {site && (
                              <a href={site} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="ml-1.5 inline-flex items-center gap-0.5 text-accent hover:underline">
                                {s.host} <ExternalLink size={9} />
                              </a>
                            )}
                          </p>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 align-top text-ink-soft">
                        <div className="flex min-w-0 items-center gap-1">
                          {s.email ? (
                            <>
                              <span className="min-w-0 truncate">{s.email}</span>
                              <CopyButton text={s.email} />
                            </>
                          ) : (
                            <span className="text-ink-faint">Нет email</span>
                          )}
                        </div>
                        {s.region && <p className="truncate text-[11px] text-ink-faint">{s.region}</p>}
                      </td>
                      <td className="px-3 py-2.5 align-top text-ink-soft">{age ?? '—'}</td>
                      <td className="px-3 py-2.5 align-top text-ink-soft">{s.finances ? formatMoney(s.finances.revenue) : '—'}</td>
                      <td className="px-3 py-2.5 align-top text-ink-soft">{s.finances ? formatMoney(s.finances.profit) : '—'}</td>
                      <td className="px-3 py-2.5 align-top">
                        {s.registry ? (
                          <span className={`text-[11px] ${s.registry.is_active === false ? 'text-danger' : 'text-success'}`}>
                            {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
                          </span>
                        ) : (
                          <span className="text-[11px] text-ink-faint">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 align-top">
                        <div className="flex items-center gap-1.5">
                          <Badge tone={mailMeta.tone}>{mailMeta.label}</Badge>
                          {s.unread_count > 0 && (
                            <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                              {s.unread_count}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 pr-6 align-top">
                        <div className="flex items-center justify-end gap-1">
                          {checko && (
                            <a
                              href={checko}
                              target="_blank"
                              rel="noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              title="Профиль на Checko"
                              className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-surface-hover"
                            >
                              <img src={checkoIcon} alt="Checko" className="h-4 w-4" />
                            </a>
                          )}
                          {s.email && (
                            <button
                              type="button"
                              onClick={() => setQuickComposeId(s.id)}
                              title="Написать"
                              aria-label="Написать"
                              className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-subtle text-accent transition-colors hover:bg-accent hover:text-white"
                            >
                              <Send size={13} />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => openThread(s.id)}
                            title="Переписка"
                            aria-label="Переписка"
                            className="flex h-7 w-7 items-center justify-center rounded-full bg-info-subtle text-info transition-colors hover:bg-info hover:text-white"
                          >
                            <MessageSquareText size={13} />
                          </button>
                          <button
                            type="button"
                            disabled={irrelevantId === s.id}
                            onClick={() => void markIrrelevant(s.id)}
                            title="Не подходит — убрать из подходящих для этой заявки"
                            aria-label="Не подходит"
                            className="flex h-7 w-7 items-center justify-center rounded-full bg-danger-subtle text-danger transition-colors hover:bg-danger hover:text-white disabled:opacity-50"
                          >
                            <Ban size={13} />
                          </button>
                        </div>
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
