import { Inbox, ListChecks, MessageSquareText, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import { formatCompanyName } from '../../lib/format';
import type { MessageSearchResult, RequestListItem, ThreadSummary } from '../../lib/types';

function snippetAround(text: string, needle: string, radius = 60): string {
  const idx = text.toLowerCase().indexOf(needle.toLowerCase());
  if (idx === -1) return text.slice(0, radius * 2).trim();
  const start = Math.max(0, idx - radius);
  const end = Math.min(text.length, idx + needle.length + radius);
  return `${start > 0 ? '…' : ''}${text.slice(start, end).trim()}${end < text.length ? '…' : ''}`;
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [requests, setRequests] = useState<RequestListItem[] | null>(null);
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [messageResults, setMessageResults] = useState<MessageSearchResult[]>([]);
  const [searchingMessages, setSearchingMessages] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQuery('');
    setMessageResults([]);
    Promise.all([api.listRequests(), api.listThreads()])
      .then(([r, t]) => {
        setRequests(r.items);
        setThreads(t.items);
      })
      .catch(() => {
        setRequests([]);
        setThreads([]);
      });
  }, [open]);

  useEffect(() => {
    const trimmed = query.trim();
    if (!open || trimmed.length < 2) {
      setMessageResults([]);
      return;
    }
    setSearchingMessages(true);
    const handle = setTimeout(() => {
      api
        .searchMessages(trimmed)
        .then((res) => setMessageResults(res.items))
        .catch(() => setMessageResults([]))
        .finally(() => setSearchingMessages(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [open, query]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  const q = query.trim().toLowerCase();
  const matchedRequests = useMemo(() => {
    if (!requests) return [];
    const list = q ? requests.filter((r) => r.name.toLowerCase().includes(q)) : requests;
    return list.slice(0, 6);
  }, [requests, q]);
  const matchedThreads = useMemo(() => {
    if (!threads) return [];
    const list = q
      ? threads.filter((t) => t.supplier_name.toLowerCase().includes(q) || t.request_name.toLowerCase().includes(q) || t.subject.toLowerCase().includes(q))
      : threads;
    return list.slice(0, 6);
  }, [threads, q]);

  if (!open) return null;

  const loading = requests === null || threads === null;
  const nothingFound = !loading && !searchingMessages && matchedRequests.length === 0 && matchedThreads.length === 0 && messageResults.length === 0;

  function goToRequest(name: string) {
    navigate(`/requests?q=${encodeURIComponent(name)}`);
    onClose();
  }
  function goToThread(id: number, opts?: { messageId: number; query: string }) {
    const params = new URLSearchParams({ thread: String(id) });
    if (opts) {
      params.set('highlight', String(opts.messageId));
      params.set('q', opts.query);
    }
    navigate(`/messages?${params.toString()}`);
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Глобальный поиск"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[12vh] backdrop-blur-[2px]"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-[520px] animate-modal-in overflow-hidden rounded-xl border border-border bg-surface shadow-2xl">
        <div className="flex items-center gap-2.5 border-b border-border px-4">
          <Search size={15} className="shrink-0 text-ink-faint" />
          <input
            autoFocus
            aria-label="Поиск по заявкам, поставщикам, перепискам и тексту писем"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Заявки, поставщики, переписки, текст письма…"
            className="h-11 w-full bg-transparent text-[13.5px] outline-none placeholder:text-ink-faint"
          />
          <kbd className="shrink-0 rounded border border-border-strong px-1.5 py-0.5 text-[10px] text-ink-faint">Esc</kbd>
        </div>

        <div className="max-h-[50vh] overflow-y-auto py-1.5">
          {loading && <p className="px-4 py-3 text-[12.5px] text-ink-muted">Загружаем…</p>}
          {nothingFound && <p className="px-4 py-3 text-[12.5px] text-ink-muted">Ничего не нашлось по «{query}».</p>}

          {matchedRequests.length > 0 && (
            <div className="px-2 pb-1.5 pt-1">
              <p className="px-2 pb-1 text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">Заявки</p>
              {matchedRequests.map((r) => (
                <button
                  key={r.id}
                  onClick={() => goToRequest(r.name)}
                  className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left hover:bg-surface-hover"
                >
                  <ListChecks size={14} className="shrink-0 text-ink-faint" />
                  <span className="min-w-0 flex-1 truncate text-[13px] text-ink">{r.name}</span>
                  <span className="shrink-0 text-[11px] text-ink-faint">№{r.id}</span>
                </button>
              ))}
            </div>
          )}

          {matchedThreads.length > 0 && (
            <div className="px-2 pb-1.5 pt-1">
              <p className="px-2 pb-1 text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">Переписки</p>
              {matchedThreads.map((t) => (
                <button
                  key={t.id}
                  onClick={() => goToThread(t.id)}
                  className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left hover:bg-surface-hover"
                >
                  <Inbox size={14} className="shrink-0 text-ink-faint" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] text-ink">{formatCompanyName(t.supplier_name)}</p>
                    <p className="truncate text-[11px] text-ink-faint">{t.request_name}</p>
                  </div>
                  {t.unread_count > 0 && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />}
                </button>
              ))}
            </div>
          )}

          {query.trim().length >= 2 && (searchingMessages || messageResults.length > 0) && (
            <div className="px-2 pb-1.5 pt-1">
              <p className="px-2 pb-1 text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">
                Сообщения {searchingMessages && '· ищем…'}
              </p>
              {messageResults.map((m) => (
                <button
                  key={m.message_id}
                  onClick={() => goToThread(m.thread_id, { messageId: m.message_id, query: query.trim() })}
                  className="flex w-full items-start gap-2.5 rounded-md px-2.5 py-2 text-left hover:bg-surface-hover"
                >
                  <MessageSquareText size={14} className="mt-0.5 shrink-0 text-ink-faint" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] text-ink">
                      {formatCompanyName(m.supplier_name)} <span className="text-ink-faint">· {m.request_name}</span>
                    </p>
                    <p className="truncate text-[11px] text-ink-faint">{snippetAround(m.body_text, query.trim())}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
