import { ArrowLeft, Ban, Inbox, MessageSquareText, Package, RotateCw } from 'lucide-react';
import { useState } from 'react';
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
import { useApiData } from '../lib/useApiData';

export function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const requestId = Number(id);
  const navigate = useNavigate();
  const state = useApiData(() => api.getRequestDetail(requestId), [requestId]);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const [irrelevantId, setIrrelevantId] = useState<number | null>(null);

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

  const { request, positions, items: suppliers } = state.data;
  const statusMeta = requestStatusMeta[request.status];

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
        <div className="px-6 pb-4">
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

      <div className="flex-1 overflow-auto border-t border-border">
        {suppliers.length === 0 ? (
          <EmptyState icon={Inbox} title="Поставщики ещё не найдены" description="Запустите поиск, чтобы система нашла кандидатов." />
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
              {suppliers.map((s) => {
                const mailMeta = supplierMailStatusMeta[s.mail_status_raw] ?? supplierMailStatusMeta.not_sent;
                return (
                  <tr key={s.id} className="border-b border-border last:border-0 hover:bg-surface-hover">
                    <td className="px-3 py-2.5 pl-6 align-middle">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{formatCompanyName(s.name)}</p>
                        <p className="truncate text-[11px] text-ink-muted">{s.email || s.host}</p>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 align-middle text-ink-soft">{s.region || '—'}</td>
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
