import { ArrowLeft, Ban, Inbox, MessageSquareText, Package, RotateCw, Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { QuickAddTaskButton } from '../components/QuickAddTaskButton';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { formatCompanyName } from '../lib/format';
import { requestStatusMeta, supplierMailStatusMeta } from '../lib/statusMeta';
import type { RequestSupplierRow } from '../lib/types';
import { useApiData } from '../lib/useApiData';

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

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 px-6 pt-5">
        <Link to="/requests" className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink">
          <ArrowLeft size={13} />
          Заявки
        </Link>
      </div>

      <PageHeader
        title={request.name}
        description={`№${request.id} · ${request.sender_name}${request.company_name ? ` · ${request.company_name}` : ''}`}
        actions={
          <div className="flex items-center gap-2">
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

      {retryError && <p className="px-6 pb-2 text-[12px] text-danger">{retryError}</p>}

      {request.description && <p className="px-6 pb-3 text-[12.5px] text-ink-soft">{request.description}</p>}

      {positions.length > 0 && (
        <div className="px-6 pb-3">
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

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border px-6 py-2.5 text-[11.5px] text-ink-muted">
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

      <div className="flex flex-wrap items-center gap-2 border-t border-border px-6 py-2.5">
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

      <div className="flex-1 overflow-auto border-t border-border">
        {suppliers.length === 0 ? (
          <EmptyState icon={Inbox} title="Поставщики ещё не найдены" description="Запустите поиск, чтобы система нашла кандидатов." />
        ) : visible.length === 0 ? (
          <EmptyState icon={Search} title="Ничего не найдено" description="Попробуйте другой фильтр или запрос." />
        ) : (
          <table className="w-full border-collapse text-[12.5px]">
            <thead className="sticky top-0 z-10 bg-canvas">
              <tr className="border-b border-border">
                {['Поставщик', 'Регион', 'ИНН', 'Статус письма', ''].map((h) => (
                  <th key={h} className="whitespace-nowrap px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted first:pl-6 last:pr-6">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((s) => {
                const mailMeta = supplierMailStatusMeta[s.mail_status] ?? supplierMailStatusMeta.not_sent;
                return (
                  <tr key={s.id} className="border-b border-border last:border-0 hover:bg-surface-hover">
                    <td className="px-3 py-2.5 pl-6 align-middle">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{formatCompanyName(s.name)}</p>
                        <p className="truncate text-[11px] text-ink-muted">{s.email || s.host || 'Нет контакта'}</p>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 align-middle text-ink-soft">
                      {s.region || '—'}
                      {s.registry && (
                        <p className={`text-[10.5px] ${s.registry.is_active === false ? 'text-danger' : 'text-ink-faint'}`}>
                          {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2.5 align-middle text-ink-soft">{s.inn || '—'}</td>
                    <td className="px-3 py-2.5 align-middle">
                      <div className="flex items-center gap-1.5">
                        <Badge tone={mailMeta.tone}>{mailMeta.label}</Badge>
                        {s.unread_count > 0 && (
                          <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">
                            {s.unread_count}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 pr-6 align-middle">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button variant="ghost" size="sm" icon={<MessageSquareText size={13} />} onClick={() => openThread(s.id)}>
                          Переписка
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={<Ban size={13} />}
                          disabled={irrelevantId === s.id}
                          onClick={() => void markIrrelevant(s.id)}
                          title="Убрать из подходящих для этой заявки"
                        >
                          Не подходит
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
