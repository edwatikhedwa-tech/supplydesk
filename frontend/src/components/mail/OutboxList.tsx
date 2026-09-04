import { useEffect, useMemo, useState } from 'react';
import { Clock3, Mail, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, displayCorrespondenceSupplierName, formatRelativeDate } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';
import { getThreadDisplayStatus } from '@/components/mail/threadStatus';
import { ThreadMetadataControls } from '@/components/mail/ThreadMetadataControls';
import { Button } from '@/components/ui/Button';
import { Count, StatusBadge } from '@/components/ui/StatusBadge';

interface OutboxListProps {
  selectedThreadKey: string | null;
  onSelectThread: (thread: ThreadSummary) => void;
  refreshKey: number;
  searchInput: string;
  onMetadataChange: (thread: ThreadSummary, patch: { important?: boolean; priority?: 1 | 2 | 3 | null }) => Promise<void>;
}

export function OutboxList({ selectedThreadKey, onSelectThread, refreshKey, searchInput, onMetadataChange }: OutboxListProps) {
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
      'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[400px] 2xl:w-[420px] xl:flex',
      selectedThreadKey ? 'hidden' : 'flex',
    )}>
      <div className="border-b border-ink-100 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink-900">Очередь отправки</h2>
            <p className="mt-0.5 text-xs text-ink-500">Письма ещё не переданы поставщикам</p>
          </div>
          {!loading && !error && <Count value={visibleThreads.length} label="Количество писем в очереди" />}
        </div>
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
              <div key={key} className={cn('flex items-start', selected ? 'bg-accent-50/50' : 'hover:bg-ink-50')}>
                <button
                  type="button"
                  onClick={() => onSelectThread(thread)}
                  aria-label={`${supplierLabel}: ${thread.subject}. ${status.label}`}
                  className={cn('min-w-0 flex-1 border-l-2 px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent-400', selected ? 'border-accent-500' : 'border-transparent')}
                >
                <div className="flex items-start gap-3">
                  <Clock3 size={16} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="min-w-0 truncate text-sm font-semibold text-ink-800" title={thread.supplier_name || undefined}>{supplierLabel}</span>
                      <span className="shrink-0 text-xs text-ink-500">{formatRelativeDate(thread.last_message_at)}</span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-ink-600">{thread.subject}</p>
                    <div className="mt-1.5 flex min-w-0 items-center gap-2">
                      <StatusBadge label={status.label} tone={status.tone} title={status.title} />
                      <span className="min-w-0 flex-1 truncate text-xs text-ink-500">{thread.request_name}</span>
                    </div>
                  </div>
                </div>
                </button>
                <ThreadMetadataControls important={thread.is_important} priority={thread.priority} onChange={(patch) => onMetadataChange(thread, patch)} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
