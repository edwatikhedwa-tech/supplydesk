import { useEffect, useState } from 'react';
import { AlertTriangle, Inbox, MessageCircle, RefreshCw, Plus, Search } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { pluralize } from '@/lib/utils';
import type { DashboardSummary, RequestStatus } from '@/lib/types';

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
    <Link to={to} className={`block rounded-2xl border p-5 shadow-soft transition hover:-translate-y-0.5 hover:shadow-panel ${card}`}>
      <div className="flex items-start justify-between">
        <div>
          <div className={`text-xs font-semibold ${active ? 'text-white' : 'text-ink-500'}`}>{label}</div>
          <div className="mt-2 text-[30px] font-bold tracking-tight">{value}</div>
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${active ? 'bg-white/15' : 'bg-ink-100 text-ink-500'}`}>
          <Icon size={18} />
        </div>
      </div>
    </Link>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = () => {
    setRefreshing(true);
    return api
      .dashboardSummary()
      .then(setSummary)
      .finally(() => {
        setRefreshing(false);
        setLoading(false);
      });
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-ink-400">Загрузка…</div>;
  }

  const requests = summary?.requests ?? [];
  const kpis = summary?.kpis ?? { active_requests: 0, searching_requests: 0, new_replies: 0, attention: 0 };

  return (
    <div className="min-h-screen px-6 py-7 lg:px-10 lg:py-10">
      <div className="mx-auto max-w-[1600px] space-y-8">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <h1 className="text-[28px] font-bold tracking-tight">Дашборд</h1>
            <p className="mt-1 text-sm text-ink-500">Всё важное по текущим заявкам — в одном месте.</p>
          </div>
          <div className="flex items-center rounded-xl border border-ink-200/80 bg-white px-3 py-2 shadow-soft">
            <button onClick={load} disabled={refreshing} className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-bold text-accent-600 hover:bg-accent-50 disabled:opacity-50">
              <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />Обновить
            </button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Активные заявки" value={kpis.active_requests} icon={Inbox} to="/requests" />
          <Metric label="В поиске" value={kpis.searching_requests} icon={Search} to="/requests?filter=searching" />
          <Metric label="Новые ответы" value={kpis.new_replies} icon={MessageCircle} to="/messages" active={kpis.new_replies > 0} />
          <Metric label="Требует внимания" value={kpis.attention} icon={AlertTriangle} to="/messages" active={kpis.attention > 0} tone="warning" />
        </div>

        <section className="overflow-hidden rounded-2xl border border-ink-200/80 bg-white shadow-soft">
          <div className="flex flex-col justify-between gap-4 border-b border-ink-100 px-6 py-5 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-base font-bold">Мои заявки</h2>
              <p className="mt-1 text-xs text-ink-500">Последние запросы и их состояние</p>
            </div>
            <button onClick={() => navigate('/requests/new')} className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent-600 px-4 py-2.5 text-xs font-bold text-white shadow-soft transition hover:bg-accent-700">
              <Plus size={16} />Новая заявка
            </button>
          </div>
          {requests.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-ink-400">Заявок пока нет</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left">
                {/* Same width discipline as /requests: only the name column
                    absorbs slack, numbers are right-aligned and tabular. */}
                <thead>
                  <tr className="border-b border-ink-200 bg-ink-50 text-[11px] font-semibold uppercase tracking-wider text-ink-600">
                    <th className="w-full px-6 py-3.5">Заявка</th>
                    <th className="w-32 px-4 py-3.5">Статус</th>
                    <th className="w-28 px-4 py-3.5 text-right">Поставщики</th>
                    <th className="w-20 px-4 py-3.5 text-right">Ответы</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {requests.slice(0, 8).map((request) => (
                    <tr key={request.id} onClick={() => navigate(`/requests/${request.id}`)} className="group cursor-pointer transition hover:bg-accent-50/40">
                      <td className="px-6 py-4">
                        <Link to={`/requests/${request.id}`} onClick={(e) => e.stopPropagation()} className="block">
                          <div className="text-[13px] font-bold text-ink-800 group-hover:text-accent-700">{request.name}</div>
                          <div className="mt-1 text-[11px] text-ink-500">#{request.id} · {request.positions_count} {pluralize(request.positions_count, 'позиция', 'позиции', 'позиций')}</div>
                        </Link>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${REQUEST_STATUS_META[request.status].className}`}>{REQUEST_STATUS_META[request.status].label}</span>
                      </td>
                      <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.suppliers_count}</td>
                      <td className="px-4 py-4 text-right text-sm font-semibold tabular-nums text-ink-700">{request.replies_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
