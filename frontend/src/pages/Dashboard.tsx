import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, ChevronDown, Inbox, Loader2, Mail, MessageCircle, RefreshCw, Plus, Search } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError, api } from '@/lib/api';
import { formatFullDate, pluralize } from '@/lib/utils';
import { EmailRenderer } from '@/components/mail/EmailRenderer';
import type { DashboardSummary, InboxConversation, InboxPreview, RequestListItem, RequestStatus } from '@/lib/types';

const REQUEST_STATUS_META: Record<RequestStatus, { label: string; className: string }> = {
  draft: { label: 'Черновик', className: 'bg-ink-100 text-ink-600' },
  searching: { label: 'В поиске', className: 'bg-accent-50 text-accent-700' },
  updating: { label: 'Обновляется', className: 'bg-accent-50 text-accent-700' },
  completed: { label: 'Завершена', className: 'bg-emerald-50 text-emerald-700' },
  error: { label: 'Ошибка', className: 'bg-rose-50 text-rose-700' },
};

function Metric({
  label, value, icon: Icon, to, active = false, tone = 'accent',
}: { label: string; value: number; icon: typeof Search; to: string; active?: boolean; tone?: 'accent' | 'warning' }) {
  // Colored only when the value is nonzero and worth acting on — a neutral
  // tile with a 0 shouldn't compete visually with one that needs attention.
  const card = !active
    ? 'border-ink-200/80 bg-white'
    : tone === 'warning'
      ? 'border-amber-500 bg-amber-500 text-white'
      : 'border-accent-600 bg-accent-600 text-white';
  return (
    <Link to={to} className={`block rounded-xl border p-5 shadow-soft transition hover:-translate-y-0.5 hover:shadow-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2 ${card}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className={`text-xs font-semibold ${active ? 'text-white' : 'text-ink-500'}`}>{label}</div>
          <div className="mt-2 text-metric font-bold">{value}</div>
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${active ? 'bg-white/15' : 'bg-ink-100 text-ink-500'}`}>
          <Icon size={18} />
        </div>
      </div>
    </Link>
  );
}

function DashboardLoading() {
  return (
    <div className="dashboard-shell min-h-screen px-4 py-6 sm:px-6 lg:px-10 lg:py-10" aria-label="Загрузка дашборда">
      <div className="mx-auto max-w-[1600px] space-y-8">
        <div className="space-y-3">
          <div className="skeleton h-8 w-44 rounded-lg" />
          <div className="skeleton h-4 w-80 max-w-full rounded" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4].map((item) => <div key={item} className="skeleton h-[116px] rounded-xl" />)}
        </div>
        <div className="overflow-hidden rounded-xl border border-ink-200/80 bg-white">
          <div className="skeleton h-20 border-b border-ink-100" />
          <div className="space-y-4 p-6">
            {[1, 2, 3, 4].map((item) => <div key={item} className="skeleton h-12 rounded-lg" />)}
          </div>
        </div>
      </div>
    </div>
  );
}

function DashboardError({ message, onRetry, retrying }: { message: string; onRetry: () => void; retrying: boolean }) {
  return (
    <div className="dashboard-shell flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <div role="alert" className="w-full max-w-md rounded-xl border border-rose-200 bg-white p-7 text-center shadow-panel">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600">
          <AlertTriangle size={22} />
        </div>
        <h1 className="mt-5 text-lg font-bold text-ink-900">Не удалось загрузить дашборд</h1>
        <p className="mt-2 text-sm leading-6 text-ink-500">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="mt-6 inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-sm font-bold text-white shadow-soft transition hover:bg-accent-700 disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
        >
          <RefreshCw size={16} className={retrying ? 'animate-spin' : ''} />
          Повторить
        </button>
      </div>
    </div>
  );
}

function RequestStatus({ request }: { request: RequestListItem }) {
  const meta = REQUEST_STATUS_META[request.status];
  return <span className={`inline-flex shrink-0 rounded-full px-2.5 py-1 text-xs font-bold ${meta.className}`}>{meta.label}</span>;
}

interface UnmatchedMailCardProps {
  item: InboxPreview;
  expanded: boolean;
  message?: InboxConversation;
  loading: boolean;
  error?: string;
  onToggle: () => void;
  onRetry: () => void;
}

function UnmatchedMailCard({ item, expanded, message, loading, error, onToggle, onRetry }: UnmatchedMailCardProps) {
  return (
    <article className="border-b border-ink-100 last:border-b-0">
      <button
        type="button"
        aria-expanded={expanded}
        aria-controls={`dashboard-inbox-${item.id}`}
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition hover:bg-amber-50/60 focus-visible:relative focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500 sm:px-6"
      >
        <div className="relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
          <Mail size={15} />
          {item.unread && <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-white" title="Непрочитанное письмо" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-bold text-ink-800">{item.from_email}</div>
          <div className="truncate text-xs text-ink-500">{item.subject || '(без темы)'}</div>
        </div>
        <time dateTime={item.received_at} className="shrink-0 text-xs text-ink-400">
          {new Date(item.received_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
        </time>
        <ChevronDown size={16} className={`shrink-0 text-ink-400 transition-transform ${expanded ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>

      {expanded && (
        <div id={`dashboard-inbox-${item.id}`} role="region" aria-label={`Письмо от ${item.from_email}`} className="border-t border-amber-100 bg-amber-50/30 px-5 py-4 sm:px-6">
          {loading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-ink-500" role="status">
              <Loader2 size={16} className="animate-spin text-amber-600" /> Загружаем письмо…
            </div>
          ) : error ? (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs text-rose-700">
              <span>{error}</span>
              <button type="button" onClick={onRetry} className="font-bold text-rose-800 underline underline-offset-2 hover:no-underline">Повторить</button>
            </div>
          ) : message ? (
            <div className="rounded-xl border border-ink-200 bg-white p-4 shadow-sm sm:p-5">
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-ink-100 pb-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-ink-900">{message.from_email}</p>
                  <p className="mt-1 break-words text-xs text-ink-500">Кому: {message.to_email}</p>
                </div>
                <time dateTime={message.received_at} className="text-xs text-ink-400">{formatFullDate(message.received_at)}</time>
              </div>
              <div className="overflow-hidden">
                <EmailRenderer html={message.body_html} text={message.body_text} hasRemoteImages={message.has_remote_images} />
              </div>
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-ink-100 pt-3">
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700">
                  {item.unread && <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />} {item.unread ? 'Непрочитанное письмо без привязки' : 'Письмо без привязки'}
                </span>
                <Link to={`/messages?tab=unmatched&inbox=${item.id}`} className="inline-flex min-h-10 items-center gap-1 px-1 text-xs font-bold text-accent-700 hover:underline">
                  Открыть в переписке <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </article>
  );
}

function RequestCard({ request }: { request: RequestListItem }) {
  return (
    <Link
      to={`/requests/${request.id}`}
      className="block px-5 py-4 transition hover:bg-accent-50/40 focus-visible:relative focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-500 sm:px-6"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-bold text-ink-800">{request.name}</div>
          <div className="mt-1 text-xs text-ink-500">#{request.id} · {request.positions_count} {pluralize(request.positions_count, 'позиция', 'позиции', 'позиций')}</div>
        </div>
        <RequestStatus request={request} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
        <div>
          <div className="text-ink-400">Поставщики</div>
          <div className="mt-1 font-bold tabular-nums text-ink-700">{request.suppliers_count}</div>
        </div>
        <div>
          <div className="text-ink-400">Ответы</div>
          <div className="mt-1 font-bold tabular-nums text-ink-700">{request.replies_count}</div>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <div className="text-ink-400">Обновление</div>
          <div className="mt-1 truncate font-semibold text-ink-600" title={request.updated_at || undefined}>{request.updated_at ? new Date(request.updated_at).toLocaleDateString('ru-RU') : '—'}</div>
        </div>
      </div>
      {request.status === 'error' && (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-rose-100 bg-rose-50 px-3 py-2.5 text-xs font-semibold text-rose-700">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <span>Заявка завершилась с ошибкой. Откройте её, чтобы проверить детали.</span>
        </div>
      )}
    </Link>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [unmatchedPreview, setUnmatchedPreview] = useState<InboxPreview[]>([]);
  const [expandedMailIds, setExpandedMailIds] = useState<Set<number>>(new Set());
  const [unmatchedMessages, setUnmatchedMessages] = useState<Record<number, InboxConversation>>({});
  const [loadingMailIds, setLoadingMailIds] = useState<Set<number>>(new Set());
  const [mailErrors, setMailErrors] = useState<Record<number, string>>({});

  const loadInboxMessage = useCallback(async (messageId: number) => {
    setLoadingMailIds((current) => new Set(current).add(messageId));
    setMailErrors((current) => {
      const next = { ...current };
      delete next[messageId];
      return next;
    });
    try {
      // Opening the conversation marks the incoming message as read on the
      // server, just like the request-thread reader does.
      const conversation = await api.inboxConversation(messageId);
      setUnmatchedMessages((current) => ({ ...current, [messageId]: conversation }));
      setUnmatchedPreview((current) => current.map((item) => item.id === messageId ? { ...item, unread: false } : item));
    } catch (error) {
      setMailErrors((current) => ({
        ...current,
        [messageId]: error instanceof ApiError ? error.message : 'Не удалось загрузить письмо.',
      }));
    } finally {
      setLoadingMailIds((current) => {
        const next = new Set(current);
        next.delete(messageId);
        return next;
      });
    }
  }, []);

  const toggleInboxMessage = useCallback((item: InboxPreview) => {
    setExpandedMailIds((current) => {
      const next = new Set(current);
      const opening = !next.has(item.id);
      if (opening) next.add(item.id);
      else next.delete(item.id);
      return next;
    });
    if (!unmatchedMessages[item.id] && !loadingMailIds.has(item.id)) {
      void loadInboxMessage(item.id);
    }
  }, [loadInboxMessage, loadingMailIds, unmatchedMessages]);

  const load = useCallback(async () => {
    setRetrying(true);
    try {
      const nextSummary = await api.dashboardSummary();
      setSummary(nextSummary);
      setErrorMessage(null);
      setLastUpdatedAt(new Date());
      // Отдельный, необязательный запрос: если он не удастся, дашборд не
      // должен показывать полноэкранную ошибку из-за виджета-подсказки.
      if (nextSummary.kpis.unmatched_mail > 0) {
        api.listInboxPreview().then((res) => {
          // На дашборде показываем только три последних письма.
          // Они намеренно закрыты: тело загружается только после клика.
          setUnmatchedPreview(res.items.slice(0, 3));
          setExpandedMailIds(new Set());
          setUnmatchedMessages({});
          setMailErrors({});
        }).catch(() => {
          setUnmatchedPreview([]);
          setExpandedMailIds(new Set());
          setUnmatchedMessages({});
        });
      } else {
        setUnmatchedPreview([]);
        setExpandedMailIds(new Set());
        setUnmatchedMessages({});
      }
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : 'Проверьте соединение и попробуйте ещё раз.');
    } finally {
      setRetrying(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <DashboardLoading />;
  }

  if (errorMessage && !summary) {
    return <DashboardError message={errorMessage} onRetry={() => { void load(); }} retrying={retrying} />;
  }

  const requests = summary?.requests ?? [];
  const kpis = summary?.kpis ?? { active_requests: 0, searching_requests: 0, new_replies: 0, attention: 0, unmatched_mail: 0 };
  const visibleRequests = requests.slice(0, 8);
  const updatedLabel = lastUpdatedAt
    ? `Обновлено в ${lastUpdatedAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`
    : 'Данные ещё не обновлялись';

  return (
    <div className="dashboard-shell min-h-screen px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
      <div className="mx-auto max-w-[1600px] space-y-8">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <h1 className="text-page-title font-bold">Дашборд</h1>
            <p className="mt-1 text-sm text-ink-500">Всё важное по текущим заявкам — в одном месте.</p>
          </div>
          <span className="text-xs font-medium text-ink-400" aria-live="polite">{updatedLabel}</span>
        </div>

        {errorMessage && summary && (
          <div role="alert" className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2">
              <AlertTriangle size={17} className="mt-0.5 shrink-0 text-amber-600" />
              <span>Не удалось обновить данные. Показана последняя успешная версия.</span>
            </div>
            <button type="button" onClick={() => { void load(); }} disabled={retrying} className="inline-flex min-h-9 items-center justify-center gap-1.5 self-start rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-bold text-amber-800 hover:bg-amber-100 disabled:opacity-50 sm:self-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2">
              <RefreshCw size={14} className={retrying ? 'animate-spin' : ''} />Повторить
            </button>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Активные заявки" value={kpis.active_requests} icon={Inbox} to="/requests" />
          <Metric label="В поиске" value={kpis.searching_requests} icon={Search} to="/requests?filter=searching" />
          <Metric label="Новые ответы" value={kpis.new_replies} icon={MessageCircle} to="/messages" active={kpis.new_replies > 0} />
          <Metric label="Требует внимания" value={kpis.attention} icon={AlertTriangle} to="/requests?filter=error" active={kpis.attention > 0} tone="warning" />
        </div>

        {unmatchedPreview.length > 0 && (
          <section className="overflow-hidden rounded-xl border border-amber-200 bg-white shadow-soft">
            <div className="flex items-center justify-between gap-4 border-b border-amber-100 bg-amber-50/60 px-6 py-4">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-600" />
                <h2 className="text-sm font-bold text-amber-900">
                  Письма без привязки к заявке
                  <span className="ml-1.5 font-normal text-amber-700">({kpis.unmatched_mail})</span>
                </h2>
              </div>
              <Link to="/messages?tab=unmatched" className="inline-flex min-h-10 items-center px-1 text-xs font-bold text-amber-800 hover:underline">Все письма</Link>
            </div>
            <p className="border-b border-ink-100 px-6 py-2.5 text-xs text-ink-500">
              Система не смогла отнести эти письма ни к одной заявке — проверьте, не ответ ли это поставщика.
            </p>
            <div className="divide-y divide-ink-100">
              {unmatchedPreview.map((item) => (
                <UnmatchedMailCard
                  key={item.id}
                  item={item}
                  expanded={expandedMailIds.has(item.id)}
                  message={unmatchedMessages[item.id]}
                  loading={loadingMailIds.has(item.id)}
                  error={mailErrors[item.id]}
                  onToggle={() => toggleInboxMessage(item)}
                  onRetry={() => { void loadInboxMessage(item.id); }}
                />
              ))}
            </div>
          </section>
        )}

        <section className="overflow-hidden rounded-xl border border-ink-200/80 bg-white shadow-soft">
          <div className="flex flex-col justify-between gap-4 border-b border-ink-100 px-6 py-5 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-base font-bold">Мои заявки</h2>
              <p className="mt-1 text-xs text-ink-500">Последние {Math.min(8, requests.length)} из {requests.length} заявок</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link to="/requests" className="inline-flex min-h-10 items-center rounded-lg px-2 py-2 text-xs font-bold text-accent-700 hover:bg-accent-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2">Все заявки</Link>
              <button type="button" onClick={() => navigate('/requests/new')} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-xs font-bold text-white shadow-soft transition hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2">
                <Plus size={16} />Новая заявка
              </button>
            </div>
          </div>
          {requests.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <p className="text-sm font-semibold text-ink-700">Заявок пока нет</p>
              <p className="mt-1 text-xs text-ink-500">Создайте первую заявку, чтобы начать поиск поставщиков.</p>
              <Link to="/requests/new" className="mt-5 inline-flex min-h-10 items-center rounded-lg bg-accent-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-accent-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2">Создать заявку</Link>
            </div>
          ) : (
            <>
              <div className="hidden overflow-hidden xl:block">
                <table className="w-full table-fixed text-left">
                {/* Same width discipline as /requests: only the name column
                    absorbs slack, numbers are right-aligned and tabular. */}
                  <thead>
                    <tr className="border-b border-ink-200 bg-ink-50 text-2xs font-semibold uppercase tracking-wider text-ink-600">
                      <th scope="col" className="px-6 py-3.5">Заявка</th>
                      <th scope="col" className="w-32 px-4 py-3.5">Статус</th>
                      <th scope="col" className="w-28 px-4 py-3.5 text-right">Поставщики</th>
                      <th scope="col" className="w-20 px-4 py-3.5 text-right">Ответы</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {visibleRequests.map((request) => (
                      <tr key={request.id} className="group transition hover:bg-accent-50/40">
                        <td className="max-w-0 px-6 py-4">
                          <Link to={`/requests/${request.id}`} className="block rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2">
                            <div className="truncate text-sm font-bold text-ink-800 group-hover:text-accent-700">{request.name}</div>
                            <div className="mt-1 text-xs text-ink-500">#{request.id} · {request.positions_count} {pluralize(request.positions_count, 'позиция', 'позиции', 'позиций')}</div>
                          </Link>
                        </td>
                        <td className="px-4 py-4"><RequestStatus request={request} /></td>
                        <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.suppliers_count}</td>
                        <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.replies_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="divide-y divide-ink-100 xl:hidden">
                {visibleRequests.map((request) => <RequestCard key={request.id} request={request} />)}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
