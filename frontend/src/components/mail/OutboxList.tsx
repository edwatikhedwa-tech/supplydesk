import { useEffect, useMemo, useState } from 'react';
import { Clock3, Mail, RefreshCw, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, displayCorrespondenceSupplierName, formatRelativeDate } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';
import { getThreadDisplayStatus } from '@/components/mail/threadStatus';
import { Button } from '@/components/ui/Button';
import { Count } from '@/components/ui/StatusBadge';
import { TextField } from '@/components/ui/TextField';

interface OutboxListProps {
  selectedThreadKey: string | null;
  onSelectThread: (thread: ThreadSummary) => void;
  refreshKey: number;
  searchInput: string;
  onSearchChange: (value: string) => void;
}

export function OutboxList({ selectedThreadKey, onSelectThread, refreshKey, searchInput, onSearchChange }: OutboxListProps) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const visibleThreads = useMemo(() => {
    const query = searchInput.trim().toLowerCase();
    if (!query) return threads;
    return threads.filter((thread) => [thread.request_name, thread.supplier_name, thread.supplier_email, thread.supplier_host, thread.subject].some((value) => value.toLowerCase().includes(query)));
  }, [searchInput, threads]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api.listOutboxThreads()
      .then((res) => { if (!cancelled) setThreads(res.items); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  return (
    <div className={cn(
      'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[360px] 2xl:w-[380px] xl:flex',
      selectedThreadKey ? 'hidden' : 'flex',
    )}>
      <div className="border-b border-ink-200 px-4 pb-4 pt-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-2xs font-bold uppercase tracking-[0.16em] text-accent-700">Рабочий список</p>
            <h2 className="mt-1 text-base font-bold tracking-tight text-ink-900">Очередь отправки</h2>
            <p className="mt-0.5 text-xs text-ink-500">Письма ещё не переданы поставщикам</p>
          </div>
          {!loading && !error && <Count value={visibleThreads.length} label="Количество писем в очереди" />}
        </div>
        <TextField
          id="messages-search"
          label="Поиск по поставщику, заявке, теме или адресу"
          type="search"
          value={searchInput}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Поиск по заявке или поставщику"
          icon={Search}
          className="mt-3"
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-sm text-ink-400" role="status">Загружаем очередь…</div>
        ) : error ? (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <Mail size={30} className="mb-3 text-ink-300" />
            <p className="text-sm text-ink-500">Не удалось загрузить очередь</p>
            <Button size="sm" variant="secondary" onClick={() => window.location.reload()} className="mt-3">
              <RefreshCw size={14} /> Повторить
            </Button>
          </div>
        ) : visibleThreads.length === 0 ? (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <Clock3 size={30} className="mb-3 text-ink-300" />
            <p className="text-sm font-medium text-ink-600">Очередь пуста</p>
            <p className="mt-1 text-xs leading-5 text-ink-400">Все письма либо отправлены, либо требуют отдельной проверки.</p>
          </div>
        ) : (
          visibleThreads.map((thread) => {
            const key = `${thread.request_id}:${thread.supplier_id}`;
            const selected = selectedThreadKey === key;
            const status = getThreadDisplayStatus(thread);
            const supplierLabel = displayCorrespondenceSupplierName(thread.supplier_name) || 'Поставщик не определён';
            return (
              <div key={key} className={cn('border-b border-ink-100', selected ? 'bg-accent-50/50' : 'hover:bg-ink-50')}>
                <button
                  type="button"
                  onClick={() => onSelectThread(thread)}
                  aria-label={`${supplierLabel}: ${thread.subject}. ${status.label}`}
                  className={cn('min-w-0 w-full border-l-2 px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-400', selected ? 'border-accent-500' : 'border-transparent')}
                >
                <div className="flex items-start gap-3">
                  <Clock3 size={16} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-semibold text-ink-800" title={thread.supplier_name || undefined}>{supplierLabel}</span>
                      <span className="shrink-0 text-xs text-ink-500">{formatRelativeDate(thread.last_message_at)}</span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-ink-600">{thread.subject}</p>
                    <div className="mt-2 flex min-w-0 items-center gap-1.5 text-2xs font-medium text-ink-500">
                      <span aria-hidden="true" className={cn('h-1.5 w-1.5 rounded-full', status.tone === 'success' ? 'bg-emerald-500' : status.tone === 'warning' ? 'bg-amber-500' : status.tone === 'danger' ? 'bg-rose-500' : 'bg-ink-300')} />
                      <span title={status.title}>{status.label}</span>
                      <span className="truncate text-ink-400">· {thread.request_name}</span>
                    </div>
                  </div>
                </div>
                </button>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
