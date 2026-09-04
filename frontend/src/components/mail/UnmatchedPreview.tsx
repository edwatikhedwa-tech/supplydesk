import { useEffect, useState } from 'react';
import { GripVertical, Link as LinkIcon, Mail, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeDate } from '@/lib/utils';
import type { InboxPreview } from '@/lib/types';

interface UnmatchedPreviewProps {
  refreshKey: number;
  onShowAll: () => void;
  onOpenMessage?: (messageId: number) => void;
  onDragStart: (messageId: number) => void;
  onDragEnd: () => void;
}

export function UnmatchedPreview({ refreshKey, onShowAll, onOpenMessage, onDragStart, onDragEnd }: UnmatchedPreviewProps) {
  const [items, setItems] = useState<InboxPreview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api.listInboxPreview()
      .then((res) => { if (!cancelled) setItems(res.items.slice(0, 3)); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (!loading && !error && items.length === 0) return null;

  return (
    <section aria-labelledby="unmatched-preview-title" className="border-b border-amber-200/70 bg-amber-50/55 px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700"><Mail size={14} aria-hidden="true" /></span>
          <div className="min-w-0">
            <h2 id="unmatched-preview-title" className="truncate text-xs font-bold uppercase tracking-wide text-amber-950">Без привязки</h2>
            <p className="text-2xs text-amber-800">Нужно решение закупщика</p>
          </div>
        </div>
        <button type="button" onClick={onShowAll} className="min-h-9 shrink-0 rounded-lg px-2 text-xs font-semibold text-amber-900 hover:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400">Показать все <span aria-hidden="true">→</span></button>
      </div>
      {loading ? (
        <div className="mt-2 flex items-center gap-2 text-xs text-amber-800" role="status"><RefreshCw size={13} className="animate-spin" />Загружаем новые письма…</div>
      ) : error ? (
        <p role="alert" className="mt-2 text-xs text-rose-700">Не удалось загрузить превью.</p>
      ) : (
        <div className="mt-2 space-y-1.5">
          {items.map((item) => (
            <div
              key={item.id}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('application/x-supplydesk-inbox-id', String(item.id));
                onDragStart(item.id);
              }}
              onDragEnd={onDragEnd}
              className="group flex items-center gap-1 rounded-xl border border-amber-200 bg-white/85 p-1.5 shadow-sm transition-colors hover:border-amber-300"
              title="Перетащите письмо на заявку, чтобы начать безопасную привязку"
            >
              <span className="shrink-0 cursor-grab px-0.5 text-amber-500 group-active:cursor-grabbing"><GripVertical size={15} aria-hidden="true" /></span>
              <button type="button" onClick={() => onOpenMessage?.(item.id)} className="min-w-0 flex-1 rounded-lg px-1.5 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400">
                <div className="flex items-center gap-1.5">
                  <span className={cn('truncate text-xs', item.unread ? 'font-bold text-ink-900' : 'font-semibold text-ink-700')}>{item.from_email}</span>
                  <span className="shrink-0 text-2xs text-amber-800">{formatRelativeDate(item.received_at)}</span>
                </div>
                <p className="truncate text-2xs text-ink-600">{item.subject || '(без темы)'}</p>
              </button>
              <button type="button" onClick={() => onOpenMessage?.(item.id)} aria-label={`Связать письмо от ${item.from_email}`} className="inline-flex min-h-9 shrink-0 items-center gap-1 rounded-lg px-2 text-2xs font-bold text-amber-900 hover:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400"><LinkIcon size={12} aria-hidden="true" />Связать</button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
