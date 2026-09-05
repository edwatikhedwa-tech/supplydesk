import { AlertTriangle, ArrowRight, Inbox, MessageSquareText, PauseCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { requestGroups, threadMessages, unmatchedMail } from '../fixtures/messages';
import { requests } from '../fixtures/requests';
import { TODAY, daysFromToday, deadlineUrgency, formatRelativeTime } from '../lib/format';

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
  const activeRequests = requests.filter((r) => r.status !== 'completed');
  const attentionRequests = activeRequests
    .filter((r) => ['overdue', 'today', 'soon'].includes(deadlineUrgency(r.deadline)))
    .sort((a, b) => (daysFromToday(a.deadline) ?? 999) - (daysFromToday(b.deadline) ?? 999));

  const newReplies = requestGroups
    .flatMap((g) => g.threads.map((t) => ({ group: g, thread: t })))
    .filter(({ thread }) => thread.unread_count > 0)
    .sort((a, b) => new Date(b.thread.last_message_at).getTime() - new Date(a.thread.last_message_at).getTime());

  const staleRequests = activeRequests
    .filter((r) => {
      if (!r.updated_at) return false;
      const days = Math.round((TODAY.getTime() - new Date(r.updated_at).getTime()) / 86400000);
      return days >= 2 && r.replies_count === 0;
    })
    .sort((a, b) => new Date(a.updated_at ?? 0).getTime() - new Date(b.updated_at ?? 0).getTime());

  const totalUnread = requestGroups.reduce((sum, g) => sum + g.threads.reduce((s, t) => s + t.unread_count, 0), 0);

  const chips = [
    { label: 'Активных заявок', value: activeRequests.length },
    { label: 'Требуют внимания', value: attentionRequests.length, tone: attentionRequests.length > 0 },
    { label: 'Новых ответов', value: totalUnread, tone: totalUnread > 0 },
    { label: 'Без привязки', value: unmatchedMail.filter((m) => m.unread).length, tone: unmatchedMail.some((m) => m.unread) },
  ];

  return (
    <div className="flex h-full flex-col overflow-auto">
      <PageHeader title="Дашборд" description="Что сейчас требует внимания" />

      <div className="flex flex-wrap items-center gap-2 border-b border-border px-6 pb-4">
        {chips.map((c) => (
          <div
            key={c.label}
            className="flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1 text-[12px]"
          >
            <span className={c.tone ? 'font-semibold tabular-nums text-accent' : 'font-semibold tabular-nums text-ink-soft'}>
              {c.value}
            </span>
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
                      {r.suppliers_count - r.replies_count > 0
                        ? `${r.suppliers_count - r.replies_count} поставщиков без ответа`
                        : 'Ответили все поставщики'}
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
                      Отправлено {r.sent_count}, ответов нет · обновлено {formatRelativeTime(r.updated_at!)}
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
            {newReplies.length === 0 ? (
              <EmptyState icon={MessageSquareText} title="Нет непрочитанных ответов" />
            ) : (
              newReplies.map(({ group, thread }) => {
                const last = threadMessages[thread.id]?.at(-1);
                return (
                  <Row key={thread.id}>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12.5px] font-medium text-ink">
                        {thread.supplier_name} <span className="text-ink-faint">· {group.request_name}</span>
                      </p>
                      <p className="truncate text-[11.5px] text-ink-muted">{last?.body_text.split('\n')[0]}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge tone="accent">{thread.unread_count}</Badge>
                      <span className="w-14 text-right text-[11px] text-ink-faint">{formatRelativeTime(thread.last_message_at)}</span>
                    </div>
                  </Row>
                );
              })
            )}
          </SectionCard>

          <SectionCard title="Письма без заявки" icon={Inbox} count={unmatchedMail.length} viewAllTo="/messages">
            {unmatchedMail.slice(0, 4).map((m) => (
              <Row key={m.id}>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12.5px] font-medium text-ink">{m.subject}</p>
                  <p className="truncate text-[11.5px] text-ink-muted">{m.from_email}</p>
                </div>
                {m.suggestion ? (
                  <Badge tone="info">Похоже: {m.suggestion.supplier_name}</Badge>
                ) : (
                  <span className="text-[11px] text-ink-faint">{formatRelativeTime(m.received_at)}</span>
                )}
              </Row>
            ))}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
