import { Check, ExternalLink, StickyNote, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { EmptyState } from './ui/EmptyState';
import { SupplierCardContent } from './SupplierCardContent';

/** Opened from the Messages "Заметки" action. Contextual: the user stays on
 * the Messages screen instead of navigating away to the full /suppliers/:id
 * page -- this panel IS the supplier's card (contacts, finances, history,
 * global note), not a separate abstract notes window. See
 * docs/ui/MESSAGES_SCREEN_SPEC.md ("Карточка поставщика").
 *
 * The per-thread note (this request + this supplier specifically) is kept
 * alongside the supplier's global note rather than dropped -- it predates
 * this panel and nothing else surfaces it. */
export function SupplierCardPanel({
  requestId,
  supplierId,
  globalSupplierId,
  onClose,
  onNoteSaved,
}: {
  requestId: number;
  /** Request-scoped suppliers.id -- always present, used for the thread note. */
  supplierId: number;
  /** Global картотека id -- null until this thread's supplier is confirmed/linked. */
  globalSupplierId: number | null;
  onClose: () => void;
  onNoteSaved?: () => void;
}) {
  const [threadNote, setThreadNote] = useState('');
  const [threadNoteLoaded, setThreadNoteLoaded] = useState(false);
  const [threadNoteSaveState, setThreadNoteSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const threadNoteSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setThreadNoteLoaded(false);
    api
      .getThreadNote(requestId, supplierId)
      .then((res) => setThreadNote(res.note))
      .catch(() => setThreadNote(''))
      .finally(() => setThreadNoteLoaded(true));
  }, [requestId, supplierId]);

  function handleThreadNoteChange(value: string) {
    setThreadNote(value);
    setThreadNoteSaveState('idle');
    if (threadNoteSaveTimer.current) clearTimeout(threadNoteSaveTimer.current);
    threadNoteSaveTimer.current = setTimeout(() => {
      setThreadNoteSaveState('saving');
      api
        .saveThreadNote(requestId, supplierId, value)
        .then(() => {
          setThreadNoteSaveState('saved');
          onNoteSaved?.();
        })
        .catch(() => setThreadNoteSaveState('idle'));
    }, 500);
  }

  return (
    <div className="flex h-full w-full shrink-0 flex-col border-l border-border bg-canvas sm:w-[380px]">
      <div className="flex items-center justify-between border-b border-border bg-surface px-3.5 py-2.5">
        <span className="text-[12.5px] font-semibold text-ink">Карточка поставщика</span>
        <div className="flex items-center gap-1">
          {globalSupplierId != null && (
            <Link
              to={`/suppliers/${globalSupplierId}`}
              title="Открыть полную карточку"
              className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink"
            >
              <ExternalLink size={13} />
            </Link>
          )}
          <button type="button" onClick={onClose} aria-label="Закрыть карточку поставщика" className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink">
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <section className="border-b border-border bg-surface p-3.5">
          <h2 className="mb-2 flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
            <StickyNote size={13} />
            Заметка по этой переписке
          </h2>
          {threadNoteLoaded && (
            <textarea
              value={threadNote}
              onChange={(e) => handleThreadNoteChange(e.target.value)}
              placeholder="Например: обещал прислать сертификаты до пятницы, звонить лучше после обеда…"
              className="min-h-[80px] w-full resize-y rounded-md border border-border-strong bg-canvas px-3 py-2 text-[12.5px] leading-relaxed outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          )}
          <p className="mt-1.5 flex items-center gap-1 text-[11px] text-ink-faint">
            {threadNoteSaveState === 'saving' && 'Сохраняем…'}
            {threadNoteSaveState === 'saved' && (
              <>
                <Check size={12} className="text-success" />
                Сохранено
              </>
            )}
            {threadNoteSaveState === 'idle' && 'Видна только вам, привязана к этой переписке'}
          </p>
        </section>

        {globalSupplierId != null ? (
          <SupplierCardContent supplierId={globalSupplierId} compact />
        ) : (
          <div className="p-3.5">
            <EmptyState
              icon={StickyNote}
              title="Карточка появится после подтверждения поставщика"
              description="Пока поставщик не привязан к общему справочнику, доступна только заметка по переписке выше."
            />
          </div>
        )}
      </div>
    </div>
  );
}
