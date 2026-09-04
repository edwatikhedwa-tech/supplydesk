import { useEffect, useState } from 'react';
import { GripVertical, Link as LinkIcon, Mail, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatRelativeDate } from '@/lib/utils';
import type { InboxPreview } from '@/lib/types';
import { Button } from '@/components/ui/button';

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
    <section aria-labelledby="unmatched-preview-title" className="border-b border-ink-200 bg-ink-50/45 px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white text-amber-700 ring-1 ring-amber-200"><Mail size={14} aria-hidden="true" /></span>
          <div className="min-w-0">
            <h2 id="unmatched-preview-title" className="truncate text-xs font-bold uppercase tracking-[0.12em] text-ink-900">Без привязки</h2>
            <p className="text-2xs text-ink-500">Нужно решение закупщика</p>
          </div>
          {items.length > 0 && <span className="text-2xs font-semibold tabular-nums text-amber-700">{items.length}</span>}
        </div>
        <Button size="sm" variant="link" onClick={onShowAll} className="px-1.5 text-2xs">Показать все <span aria-hidden="true">→</span></Button>
      </div>
      {loading ? (
        <div className="mt-2 flex items-center gap-2 text-xs text-ink-500" role="status"><RefreshCw size={13} className="animate-spin" />Загружаем новые письма…</div>
      ) : error ? (
        <p role="status" aria-live="polite" className="mt-2 text-xs text-rose-700">Не удалось загрузить превью.</p>
      ) : (
        <div className="mt-2 divide-y divide-ink-200/80 border-y border-ink-200/80">
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
              className="group flex items-center gap-1 py-1.5 transition-colors hover:bg-white/70"
              title="Перетащите письмо на заявку, чтобы начать безопасную привязку"
            >
              <span className="shrink-0 cursor-grab px-0.5 text-ink-400 group-active:cursor-grabbing"><GripVertical size={15} aria-hidden="true" /></span>
              <button type="button" onClick={() => onOpenMessage?.(item.id)} className="min-w-0 flex-1 rounded-lg px-1.5 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400">
                <div className="flex items-center gap-1.5">
                  <span className={cn('truncate text-2xs', item.unread ? 'font-bold text-ink-900' : 'font-semibold text-ink-700')}>{item.from_email}</span>
                  <span className="shrink-0 text-2xs text-ink-500">{formatRelativeDate(item.received_at)}</span>
                </div>
                <p className="truncate text-2xs text-ink-500">{item.subject || '(без темы)'}</p>
              </button>
              <Button size="sm" variant="link" onClick={() => onOpenMessage?.(item.id)} aria-label={`Связать письмо от ${item.from_email}`} className="min-h-9 px-1.5 text-2xs"><LinkIcon size={12} aria-hidden="true" />Связать</Button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
