import { useEffect, useState } from 'react';
import { Clock3, Mail, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeDate } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';
import { getThreadDisplayStatus } from '@/components/mail/threadStatus';

interface OutboxListProps {
  selectedThreadKey: string | null;
  onSelectThread: (thread: ThreadSummary) => void;
  refreshKey: number;
}

export function OutboxList({ selectedThreadKey, onSelectThread, refreshKey }: OutboxListProps) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

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
      'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[360px] xl:flex',
      selectedThreadKey ? 'hidden' : 'flex',
    )}>
      <div className="border-b border-ink-100 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-ink-900">Очередь отправки</h2>
            <p className="mt-0.5 text-xs text-ink-500">Письма ещё не переданы поставщикам</p>
          </div>
          {!loading && !error && <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800 ring-1 ring-amber-200">{threads.length}</span>}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-sm text-ink-400" role="status">Загружаем очередь…</div>
        ) : error ? (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <Mail size={30} className="mb-3 text-ink-300" />
            <p className="text-sm text-ink-500">Не удалось загрузить очередь</p>
            <button type="button" onClick={() => window.location.reload()} className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-accent-700 hover:bg-accent-50">
              <RefreshCw size={14} /> Повторить
            </button>
          </div>
        ) : threads.length === 0 ? (
          <div className="flex flex-col items-center px-6 py-16 text-center">
            <Clock3 size={30} className="mb-3 text-ink-300" />
            <p className="text-sm font-medium text-ink-600">Очередь пуста</p>
            <p className="mt-1 text-xs leading-5 text-ink-400">Все письма либо отправлены, либо требуют отдельной проверки.</p>
          </div>
        ) : (
          threads.map((thread) => {
            const key = `${thread.request_id}:${thread.supplier_id}`;
            const selected = selectedThreadKey === key;
            const status = getThreadDisplayStatus(thread);
            return (
              <button
                type="button"
                key={key}
                onClick={() => onSelectThread(thread)}
                aria-label={`${thread.supplier_name || 'Поставщик не определён'}: ${thread.subject}. ${status.label}`}
                className={cn('w-full border-l-2 px-4 py-3 text-left transition-colors', selected ? 'border-accent-500 bg-accent-50/50' : 'border-transparent hover:bg-ink-50')}
              >
                <div className="flex items-start gap-3">
                  <Clock3 size={16} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-ink-800">{thread.supplier_name || 'Поставщик не определён'}</span>
                      <span className="shrink-0 text-xs text-ink-500">{formatRelativeDate(thread.last_message_at)}</span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-ink-600">{thread.subject}</p>
                    <div className="mt-1.5 flex min-w-0 items-center gap-2">
                      <span title={status.title} className={cn('inline-flex shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold ring-1', status.className)}>{status.label}</span>
                      <span className="truncate text-xs text-ink-500">{thread.request_name}</span>
                    </div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
