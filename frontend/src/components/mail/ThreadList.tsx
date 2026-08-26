import { useEffect, useMemo, useRef, useState } from 'react';
import { Mail, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeDate, pluralize } from '@/lib/utils';
import type { ThreadSummary } from '@/lib/types';

interface ThreadListProps {
  selectedThreadKey: string | null;
  onSelectThread: (thread: ThreadSummary) => void;
  refreshKey: number;
}

export function ThreadList({ selectedThreadKey, onSelectThread, refreshKey }: ThreadListProps) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [search, setSearch] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [searchInput, setSearchInput] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api
      .listThreads()
      .then((res) => {
        if (!cancelled) setThreads(res.items);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const handleSearchChange = (value: string) => {
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearch(value), 200);
  };

  const visibleThreads = useMemo(() => {
    if (!search.trim()) return threads;
    const q = search.trim().toLowerCase();
    return threads.filter(
      (t) =>
        t.subject.toLowerCase().includes(q) ||
        t.request_name.toLowerCase().includes(q) ||
        t.supplier_name.toLowerCase().includes(q) ||
        t.supplier_email.toLowerCase().includes(q)
    );
  }, [threads, search]);

  return (
    <div className="w-[360px] shrink-0 border-r border-ink-200 bg-white flex flex-col">
      <div className="px-3 pt-3 pb-2.5 border-b border-ink-100 shrink-0">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по поставщику, заявке или письму..."
            className="w-full pl-9 pr-3 py-2 text-sm bg-ink-50 border border-ink-200 rounded-lg focus:outline-none focus:border-ink-300 focus:bg-white transition-colors placeholder:text-ink-400"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-3 space-y-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="p-3 space-y-2">
                <div className="h-3 w-1/2 bg-ink-100 rounded animate-pulse" />
                <div className="h-3 w-3/4 bg-ink-100 rounded animate-pulse" />
                <div className="h-3 w-2/3 bg-ink-100 rounded animate-pulse" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="p-6 text-center">
            <p className="text-sm text-ink-500">Не удалось загрузить письма</p>
          </div>
        ) : visibleThreads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <Mail size={32} className="text-ink-300 mb-3" />
            <p className="text-sm text-ink-400">Переписки по заявкам пока нет</p>
          </div>
        ) : (
          <div className="py-1">
            {visibleThreads.map((thread) => {
              const key = `${thread.request_id}:${thread.supplier_id}`;
              const isSelected = selectedThreadKey === key;
              const hasReplies = thread.replies_count > 0;
              return (
                <button
                  key={key}
                  onClick={() => onSelectThread(thread)}
                  className={cn(
                    'w-full px-3 py-2.5 text-left transition-colors border-l-2',
                    isSelected ? 'bg-accent-50/50 border-accent-500' : 'border-transparent hover:bg-ink-50'
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <div className="pt-1 shrink-0">
                      <span
                        title={hasReplies ? 'Есть ответ от поставщика' : undefined}
                        className={cn('block w-2 h-2 rounded-full', hasReplies ? 'bg-emerald-500' : 'bg-transparent')}
                      />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2 mb-0.5">
                        <span className="text-sm truncate font-medium text-ink-700">{thread.supplier_name}</span>
                        <span className="text-[11px] text-ink-400 shrink-0">{formatRelativeDate(thread.last_message_at)}</span>
                      </div>
                      <p className="text-[13px] truncate mb-0.5 text-ink-600">{thread.subject}</p>
                      <div className="flex items-center gap-1.5 mt-1.5">
                        <span className="text-[11px] text-ink-500 bg-ink-100 px-1.5 py-0.5 rounded font-medium truncate">
                          {thread.request_name} · {thread.messages_count} {pluralize(thread.messages_count, 'письмо', 'письма', 'писем')}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
