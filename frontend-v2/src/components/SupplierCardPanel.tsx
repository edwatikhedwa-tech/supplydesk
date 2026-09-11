import { Check, ExternalLink, FileText, Loader2, Search, StickyNote, TriangleAlert, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../lib/api';
import { SupplierCardContent } from './SupplierCardContent';

/** Opened only from the Messages "Заметки" action. It keeps the active
 * request, the current-thread note and the supplier card together, so a user
 * can check the context without leaving the correspondence. See
 * docs/ui/MESSAGES_SCREEN_SPEC.md ("Карточка поставщика").
 *
 * The per-thread note (this request + this supplier specifically) is kept
 * alongside the supplier's global note rather than dropped -- it predates
 * this panel and nothing else surfaces it. */
type InnState = 'idle' | 'searching' | 'invalid' | 'not_found' | 'unavailable' | 'no_key' | 'error';

export function SupplierCardPanel({
  requestId,
  requestName,
  supplierId,
  globalSupplierId,
  onClose,
  onNoteSaved,
  onSupplierLinked,
}: {
  requestId: number;
  /** Name of the request that owns this correspondence. */
  requestName: string;
  /** Request-scoped suppliers.id -- always present, used for the thread note. */
  supplierId: number;
  /** Global картотека id -- null until this thread's supplier is confirmed/linked. */
  globalSupplierId: number | null;
  onClose: () => void;
  onNoteSaved?: () => void;
  /** Fired once a manual ИНН entry links this thread's supplier to the
   * global справочник, so the caller can refetch the thread list (updates
   * `globalSupplierId` from the outside, e.g. for the AI-context panel too). */
  onSupplierLinked?: () => void;
}) {
  const [threadNote, setThreadNote] = useState('');
  const [threadNoteLoaded, setThreadNoteLoaded] = useState(false);
  const [threadNoteSaveState, setThreadNoteSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const threadNoteSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [innValue, setInnValue] = useState('');
  const [innState, setInnState] = useState<InnState>('idle');
  const [innMessage, setInnMessage] = useState('');
  const [resolvedGlobalSupplierId, setResolvedGlobalSupplierId] = useState<number | null>(null);
  const innSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setThreadNoteLoaded(false);
    api
      .getThreadNote(requestId, supplierId)
      .then((res) => setThreadNote(res.note))
      .catch(() => setThreadNote(''))
      .finally(() => setThreadNoteLoaded(true));
  }, [requestId, supplierId]);

  useEffect(() => {
    setInnValue('');
    setInnState('idle');
    setInnMessage('');
    setResolvedGlobalSupplierId(null);
    if (innSearchTimer.current) clearTimeout(innSearchTimer.current);
  }, [requestId, supplierId]);

  const effectiveGlobalSupplierId = globalSupplierId ?? resolvedGlobalSupplierId;

  function handleInnInputChange(raw: string) {
    const digits = raw.replace(/\D/g, '').slice(0, 12);
    setInnValue(digits);
    setInnMessage('');
    if (innSearchTimer.current) clearTimeout(innSearchTimer.current);
    if (digits.length === 10 || digits.length === 12) {
      setInnState('searching');
      innSearchTimer.current = setTimeout(() => {
        void runInnLookup(digits);
      }, 600);
    } else {
      setInnState('idle');
    }
  }

  async function runInnLookup(digits: string) {
    try {
      const res = await api.setSupplierInn(requestId, supplierId, digits);
      // Backend saves the ИНН and links/creates the global supplier record
      // even when Checko itself has no data for it -- so a successful call
      // always links the thread; checko_status only decides which note we
      // show alongside the now-visible supplier card.
      if (res.global_supplier_id != null) {
        setResolvedGlobalSupplierId(res.global_supplier_id);
        onSupplierLinked?.();
      }
      if (res.checko_status === 'loaded') {
        setInnState('idle');
        setInnMessage('');
      } else if (res.checko_status === 'not_found') {
        setInnState('not_found');
        setInnMessage(res.checko_error || 'Компания с этим ИНН не найдена в Checko. ИНН сохранён.');
      } else if (res.checko_error.includes('CHECKO_KEY')) {
        setInnState('no_key');
        setInnMessage(res.checko_error);
      } else {
        setInnState('unavailable');
        setInnMessage(res.checko_error || 'Checko временно недоступен. ИНН сохранён, попробуйте обновить данные позже.');
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 400) {
        setInnState('invalid');
        setInnMessage(e.message);
      } else {
        setInnState('error');
        setInnMessage(e instanceof ApiError ? e.message : 'Не удалось выполнить проверку ИНН. Попробуйте ещё раз.');
      }
    }
  }

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
        <span className="text-[12.5px] font-semibold text-ink">Заметки и карточка поставщика</span>
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
            <FileText size={13} />
            Текущая заявка
          </h2>
          <Link
            to={`/requests/${requestId}`}
            className="group flex items-start justify-between gap-3 rounded-md border border-border bg-canvas px-3 py-2.5 text-left transition-colors hover:border-accent-border hover:bg-accent-subtle"
          >
            <span className="min-w-0">
              <span className="block text-[12.5px] font-medium leading-snug text-ink line-clamp-2">{requestName}</span>
              <span className="mt-1 block text-[11px] text-ink-faint">Заявка #{requestId}</span>
            </span>
            <ExternalLink size={13} className="mt-0.5 shrink-0 text-ink-faint transition-colors group-hover:text-accent" />
          </Link>
        </section>

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

        {effectiveGlobalSupplierId != null ? (
          <>
            {innState === 'not_found' && (
              <p className="flex items-start gap-1.5 border-b border-border bg-warning-subtle px-3.5 py-2 text-[11.5px] leading-relaxed text-warning">
                <TriangleAlert size={13} className="mt-0.5 shrink-0" />
                {innMessage}
              </p>
            )}
            {(innState === 'unavailable' || innState === 'no_key') && (
              <p className="flex items-start gap-1.5 border-b border-border bg-surface-hover px-3.5 py-2 text-[11.5px] leading-relaxed text-ink-muted">
                <TriangleAlert size={13} className="mt-0.5 shrink-0" />
                {innMessage}
              </p>
            )}
            <SupplierCardContent supplierId={effectiveGlobalSupplierId} compact />
          </>
        ) : (
          <div className="p-3.5">
            <h2 className="mb-2 flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
              <Search size={13} />
              Найти по ИНН
            </h2>
            <p className="mb-2 text-[11.5px] leading-relaxed text-ink-muted">
              Введите ИНН поставщика (10 цифр для организации, 12 — для ИП). Поиск запустится автоматически.
            </p>
            <div className="relative">
              <input
                type="text"
                inputMode="numeric"
                value={innValue}
                onChange={(e) => handleInnInputChange(e.target.value)}
                placeholder="7712345678"
                maxLength={12}
                className={`w-full rounded-md border bg-canvas px-3 py-2 text-[12.5px] leading-relaxed outline-none placeholder:text-ink-faint focus:ring-1 ${
                  innState === 'invalid' || innState === 'error'
                    ? 'border-danger-border focus:border-danger focus:ring-danger-border'
                    : 'border-border-strong focus:border-accent focus:ring-accent-border'
                }`}
              />
              {innState === 'searching' && (
                <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-ink-faint" />
              )}
            </div>
            {innState === 'idle' && innValue.length > 0 && innValue.length !== 10 && innValue.length !== 12 && (
              <p className="mt-1.5 text-[11px] text-ink-faint">Нужно 10 или 12 цифр (введено {innValue.length}).</p>
            )}
            {(innState === 'invalid' || innState === 'error') && (
              <p className="mt-1.5 flex items-start gap-1 text-[11px] text-danger">
                <TriangleAlert size={12} className="mt-0.5 shrink-0" />
                {innMessage}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
