import { Check, StickyNote, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

export function NotesPanel({
  requestId,
  supplierId,
  onClose,
  onSaved,
}: {
  requestId: number;
  supplierId: number;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [note, setNote] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setLoaded(false);
    api
      .getThreadNote(requestId, supplierId)
      .then((res) => setNote(res.note))
      .catch(() => setNote(''))
      .finally(() => setLoaded(true));
  }, [requestId, supplierId]);

  function handleChange(value: string) {
    setNote(value);
    setSaveState('idle');
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      setSaveState('saving');
      api
        .saveThreadNote(requestId, supplierId, value)
        .then(() => {
          setSaveState('saved');
          onSaved?.();
        })
        .catch(() => setSaveState('idle'));
    }, 500);
  }

  return (
    <div className="flex h-full w-full shrink-0 flex-col border-l border-border bg-surface sm:w-72">
      <div className="flex items-center justify-between border-b border-border px-3.5 py-2.5">
        <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
          <StickyNote size={14} />
          Заметки
        </span>
        <button type="button" onClick={onClose} aria-label="Закрыть заметки" className="flex h-6 w-6 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover hover:text-ink">
          <X size={14} />
        </button>
      </div>
      <div className="flex-1 p-3">
        {loaded && (
          <textarea
            value={note}
            onChange={(e) => handleChange(e.target.value)}
            placeholder="Например: обещал прислать сертификаты до пятницы, звонить лучше после обеда…"
            className="h-full min-h-[200px] w-full resize-none rounded-md border border-border-strong bg-canvas px-3 py-2 text-[12.5px] leading-relaxed outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        )}
      </div>
      <div className="flex items-center gap-1.5 border-t border-border px-3.5 py-2 text-[11px] text-ink-faint">
        {saveState === 'saving' && 'Сохраняем…'}
        {saveState === 'saved' && (
          <>
            <Check size={12} className="text-success" />
            Сохранено
          </>
        )}
        {saveState === 'idle' && 'Заметка видна только вам'}
      </div>
    </div>
  );
}
