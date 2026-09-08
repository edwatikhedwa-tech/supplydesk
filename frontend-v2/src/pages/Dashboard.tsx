import { AlertTriangle, ArrowRight, Inbox, MessageSquareText, PauseCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { api } from '../lib/api';
import { now, daysFromToday, deadlineUrgency, formatCompanyName, formatRelativeTime } from '../lib/format';
import { useApiData } from '../lib/useApiData';

function SectionCard({
  title,
  icon: Icon,
  count,
  children,
  viewAllTo,
}: {
  title: string;
  icon: typeof AlertTriangle;
  count: number;
  children: ReactNode;
  viewAllTo?: string;
}) {
  return (
    <section className="flex flex-col rounded-lg border border-border bg-surface">
      <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Icon size={14} className="text-ink-muted" />
          <h2 className="text-[12.5px] font-semibold text-ink">{title}</h2>
          <span className="tabular-nums text-[11.5px] text-ink-faint">{count}</span>
        </div>
        {viewAllTo && (
          <Link to={viewAllTo} className="flex items-center gap-0.5 text-[11.5px] font-medium text-accent hover:text-accent-hover">
            Все <ArrowRight size={11} />
          </Link>
        )}
      </header>
      <div className="flex flex-col">{children}</div>
    </section>
  );
}

function Row({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-3 border-b border-border px-4 py-2.5 last:border-0 hover:bg-surface-hover">{children}</div>;
}

export function Dashboard() {
  const dashboardState = useApiData(() => api.dashboardSummary(), []);
  const threadsState = useApiData(() => api.listThreads().then((r) => r.items), []);
  const unmatchedState = useApiData(() => api.listInboxPreview().then((r) => r.items), []);

  if (dashboardState.status === 'loading') {
    return (
      <div className="flex h-full flex-col overflow-auto">
        <PageHeader title="Дашборд" description="Что сейчас требует внимания" />
        <LoadingState label="Загружаем сводку с бэкенда…" />
      </div>
    );
  }
  if (dashboardState.status === 'error') {
    return (
      <div className="flex h-full flex-col overflow-auto">
        <PageHeader title="Дашборд" description="Что сейчас требует внимания" />
        <ErrorState message={dashboardState.message} onRetry={dashboardState.reload} />
      </div>
    );
  }

  const { kpis, requests } = dashboardState.data;
  const threads = threadsState.status === 'ready' ? threadsState.data : [];
  const unmatched = unmatchedState.status === 'ready' ? unmatchedState.data : [];

  const activeRequests = requests.filter((r) => r.status !== 'completed');
  const attentionRequests = activeRequests
    .filter((r) => ['overdue', 'today', 'soon'].includes(deadlineUrgency(r.deadline)))
    .sort((a, b) => (daysFromToday(a.deadline) ?? 999) - (daysFromToday(b.deadline) ?? 999));

  const newReplies = threads.filter((t) => t.unread_count > 0).sort((a, b) => new Date(b.last_message_at ?? 0).getTime() - new Date(a.last_message_at ?? 0).getTime());

  const staleRequests = activeRequests
    .filter((r) => {
      if (!r.updated_at) return false;
      const days = Math.round((now().getTime() - new Date(r.updated_at).getTime()) / 86400000);
      return days >= 2 && r.replies_count === 0;
    })
    .sort((a, b) => new Date(a.updated_at ?? 0).getTime() - new Date(b.updated_at ?? 0).getTime());

  const chips = [
    { label: 'Активных заявок', value: kpis.active_requests },
    { label: 'Требуют внимания', value: kpis.attention, tone: kpis.attention > 0 },
    { label: 'Новых ответов', value: kpis.new_replies, tone: kpis.new_replies > 0 },
    { label: 'Без привязки', value: kpis.unmatched_mail, tone: kpis.unmatched_mail > 0 },
  ];

  return (
    <div className="flex h-full flex-col overflow-auto">
      <PageHeader title="Дашборд" description="Что сейчас требует внимания" />

      <div className="flex flex-wrap items-center gap-2 border-b border-border px-6 pb-4">
        {chips.map((c) => (
          <div key={c.label} className="flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-[12px]">
            <span className={c.tone ? 'font-semibold tabular-nums text-accent' : 'font-semibold tabular-nums text-ink-soft'}>{c.value}</span>
            <span className="text-ink-muted">{c.label}</span>
          </div>
        ))}
      </div>

      <div className="grid flex-1 grid-cols-2 gap-4 p-6">
        <div className="flex flex-col gap-4">
          <SectionCard title="Сроки и просрочки" icon={AlertTriangle} count={attentionRequests.length} viewAllTo="/requests">
            {attentionRequests.length === 0 ? (
              <EmptyState icon={AlertTriangle} title="Просроченных и срочных заявок нет" />
            ) : (
              attentionRequests.map((r) => (
                <Row key={r.id}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-medium text-ink">{r.name}</p>
                    <p className="truncate text-[11.5px] text-ink-muted">
                      {r.suppliers_count - r.replies_count > 0 ? `${r.suppliers_count - r.replies_count} поставщиков без ответа` : 'Ответили все поставщики'}
                    </p>
                  </div>
                  <DeadlineTag deadline={r.deadline} />
                </Row>
              ))
            )}
          </SectionCard>

          <SectionCard title="Заявки без движения" icon={PauseCircle} count={staleRequests.length} viewAllTo="/requests">
            {staleRequests.length === 0 ? (
              <EmptyState icon={PauseCircle} title="Все активные заявки в работе" />
            ) : (
              staleRequests.map((r) => (
                <Row key={r.id}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-medium text-ink">{r.name}</p>
                    <p className="truncate text-[11.5px] text-ink-muted">
                      Отправлено {r.sent_count}, ответов нет · обновлено {formatRelativeTime(r.updated_at)}
                    </p>
                  </div>
                  <Badge tone="neutral">Без ответов</Badge>
                </Row>
              ))
            )}
          </SectionCard>
        </div>

        <div className="flex flex-col gap-4">
          <SectionCard title="Новые ответы" icon={MessageSquareText} count={newReplies.length} viewAllTo="/messages">
            {threadsState.status === 'loading' ? (
              <LoadingState />
            ) : threadsState.status === 'error' ? (
              <ErrorState message={threadsState.message} onRetry={threadsState.reload} />
            ) : newReplies.length === 0 ? (
              <EmptyState icon={MessageSquareText} title="Нет непрочитанных ответов" />
            ) : (
              newReplies.map((t) => (
                <Row key={t.id}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-medium text-ink">
                      {formatCompanyName(t.supplier_name)} <span className="text-ink-faint">· {t.request_name}</span>
                    </p>
                    <p className="truncate text-[11.5px] text-ink-muted">{t.subject}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge tone="accent">{t.unread_count}</Badge>
                    <span className="w-14 text-right text-[11px] text-ink-faint">{formatRelativeTime(t.last_message_at)}</span>
                  </div>
                </Row>
              ))
            )}
          </SectionCard>

          <SectionCard title="Письма без заявки" icon={Inbox} count={unmatched.length} viewAllTo="/messages">
            {unmatchedState.status === 'loading' ? (
              <LoadingState />
            ) : unmatchedState.status === 'error' ? (
              <ErrorState message={unmatchedState.message} onRetry={unmatchedState.reload} />
            ) : unmatched.length === 0 ? (
              <EmptyState icon={Inbox} title="Непривязанных писем нет" />
            ) : (
              unmatched.slice(0, 4).map((m) => (
                <Row key={m.id}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-medium text-ink">{m.subject}</p>
                    <p className="truncate text-[11.5px] text-ink-muted">{m.from_email}</p>
                  </div>
                  <span className="text-[11px] text-ink-faint">{formatRelativeTime(m.received_at)}</span>
                </Row>
              ))
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
