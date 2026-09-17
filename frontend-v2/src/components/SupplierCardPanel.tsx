import { Check, ExternalLink, FileText, Globe, Loader2, Search, StickyNote, TriangleAlert, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, type ThreadNoteVisibility, type ThreadNotes } from '../lib/api';
import { formatDateTime } from '../lib/format';
import { SupplierCardContent } from './SupplierCardContent';
import { ActivityTimeline } from './ActivityTimeline';
import type { Task } from '../lib/types';

/** Opened only from the Messages "Заметки" action. It keeps the active
 * request, the current-thread note and the supplier card together, so a user
 * can check the context without leaving the correspondence. See
 * docs/ui/MESSAGES_SCREEN_SPEC.md ("Карточка поставщика").
 *
 * The per-thread note (this request + this supplier specifically) is kept
 * alongside the supplier's global note rather than dropped -- it predates
 * this panel and nothing else surfaces it. */
type InnState = 'idle' | 'searching' | 'invalid' | 'not_found' | 'unavailable' | 'error';

export function SupplierCardPanel({
  requestId,
  requestName,
  supplierId,
  globalSupplierId,
  supplierHost,
  lastMessageAt,
  onClose,
  onNoteSaved,
  onSupplierLinked,
  contactsRefreshToken,
}: {
  requestId: number;
  /** Name of the request that owns this correspondence. */
  requestName: string;
  /** Request-scoped suppliers.id -- always present, used for the thread note. */
  supplierId: number;
  /** Global картотека id -- null until this thread's supplier is confirmed/linked. */
  globalSupplierId: number | null;
  /** The site this thread's supplier was found on -- known from the moment
   * the thread exists, well before any ИНН lookup. Lets the "Найти по ИНН"
   * dead-end (no card, no way out) still offer the one thing already known:
   * a link to the company's own site. */
  supplierHost?: string;
  lastMessageAt: string | null;
  onClose: () => void;
  onNoteSaved?: () => void;
  /** Fired once a manual ИНН entry links this thread's supplier to the
   * global справочник, so the caller can refetch the thread list (updates
   * `globalSupplierId` from the outside, e.g. for the AI-context panel too). */
  onSupplierLinked?: () => void;
  /** Bump this from the caller (e.g. after a "Связаться" contact-result
   * save) to force the supplier card's contacts to refetch immediately --
   * it has its own independent data fetch and does not otherwise know a
   * contact changed elsewhere on the page. */
  contactsRefreshToken?: number;
}) {
  const [threadNotes, setThreadNotes] = useState<ThreadNotes>({ private: null, workspace: null });
  const [threadNoteVisibility, setThreadNoteVisibility] = useState<ThreadNoteVisibility>('private');
  const [threadNoteLoaded, setThreadNoteLoaded] = useState(false);
  const [threadNoteSaveState, setThreadNoteSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [relatedTasks, setRelatedTasks] = useState<Task[]>([]);
  const threadNoteSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [innValue, setInnValue] = useState('');
  const [innState, setInnState] = useState<InnState>('idle');
  const [innMessage, setInnMessage] = useState('');
  const [resolvedGlobalSupplierId, setResolvedGlobalSupplierId] = useState<number | null>(null);
  const innSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const effectiveGlobalSupplierId = globalSupplierId ?? resolvedGlobalSupplierId;

  useEffect(() => {
    setThreadNoteLoaded(false);
    api
      .getThreadNote(requestId, supplierId)
      // A live frontend can briefly meet a backend that has not restarted to
      // pick up migration 041. Preserve the old personal note in that safe,
      // read-only compatibility window instead of rendering an empty panel.
      .then((res) => setThreadNotes(res.notes ?? {
        private: res.note ? { note: res.note, visibility: 'private', author_name: 'Вы', created_at: null, updated_at: '' } : null,
        workspace: null,
      }))
      .catch(() => setThreadNotes({ private: null, workspace: null }))
      .finally(() => setThreadNoteLoaded(true));
  }, [requestId, supplierId]);

  useEffect(() => {
    api.listTasks(true)
      .then((result) => setRelatedTasks(result.items.filter((task) => task.request_id === requestId || (effectiveGlobalSupplierId !== null && task.supplier_id === effectiveGlobalSupplierId))))
      .catch(() => setRelatedTasks([]));
  }, [requestId, effectiveGlobalSupplierId]);

  useEffect(() => {
    setInnValue('');
    setInnState('idle');
    setInnMessage('');
    setResolvedGlobalSupplierId(null);
    if (innSearchTimer.current) clearTimeout(innSearchTimer.current);
  }, [requestId, supplierId]);

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
      } else {
        setInnState('unavailable');
        setInnMessage('Проверка по Checko временно недоступна. ИНН сохранён, попробуйте обновить данные позже.');
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
    setThreadNotes((current) => ({
      ...current,
      [threadNoteVisibility]: {
        note: value,
        visibility: threadNoteVisibility,
        author_name: current[threadNoteVisibility]?.author_name || 'Вы',
        created_at: current[threadNoteVisibility]?.created_at || null,
        updated_at: current[threadNoteVisibility]?.updated_at || '',
      },
    }));
    setThreadNoteSaveState('idle');
    if (threadNoteSaveTimer.current) clearTimeout(threadNoteSaveTimer.current);
    threadNoteSaveTimer.current = setTimeout(() => {
      setThreadNoteSaveState('saving');
      api
        .saveThreadNote(requestId, supplierId, value, threadNoteVisibility)
        .then((res) => {
          setThreadNotes(res.notes);
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
          <div className="mb-2 flex gap-1 rounded-md bg-surface-hover p-0.5 text-[11px]" role="tablist" aria-label="Видимость заметки">
            {([
              ['private', 'Личная'],
              ['workspace', 'Для команды'],
            ] as const).map(([visibility, label]) => (
              <button
                key={visibility}
                type="button"
                role="tab"
                aria-selected={threadNoteVisibility === visibility}
                onClick={() => setThreadNoteVisibility(visibility)}
                className={`flex-1 rounded px-2 py-1 font-medium ${threadNoteVisibility === visibility ? 'bg-surface text-ink shadow-sm' : 'text-ink-muted hover:text-ink'}`}
              >
                {label}
              </button>
            ))}
          </div>
          {threadNoteLoaded && (
            <textarea
              value={threadNotes[threadNoteVisibility]?.note || ''}
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
            {threadNoteSaveState === 'idle' && (
              threadNotes[threadNoteVisibility]
                ? threadNoteVisibility === 'workspace'
                  ? `Для команды · последний редактор: ${threadNotes.workspace?.author_name} · изменено ${formatDateTime(threadNotes.workspace?.updated_at || new Date().toISOString())}`
                  : `Личная заметка · ${threadNotes.private?.author_name} · изменено ${formatDateTime(threadNotes.private?.updated_at || new Date().toISOString())}`
                : threadNoteVisibility === 'private'
                  ? 'Видна только вам, привязана к этой переписке'
                  : 'Видна участникам этого рабочего пространства'
            )}
          </p>
        </section>

        <ActivityTimeline lastMessageAt={lastMessageAt} notes={threadNotes} tasks={relatedTasks} />

        {effectiveGlobalSupplierId != null ? (
          <>
            {innState === 'not_found' && (
              <p className="flex items-start gap-1.5 border-b border-border bg-warning-subtle px-3.5 py-2 text-[11.5px] leading-relaxed text-warning">
                <TriangleAlert size={13} className="mt-0.5 shrink-0" />
                {innMessage}
              </p>
            )}
            {innState === 'unavailable' && (
              <p className="flex items-start gap-1.5 border-b border-border bg-surface-hover px-3.5 py-2 text-[11.5px] leading-relaxed text-ink-muted">
                <TriangleAlert size={13} className="mt-0.5 shrink-0" />
                {innMessage}
              </p>
            )}
            <SupplierCardContent supplierId={effectiveGlobalSupplierId} compact refreshToken={contactsRefreshToken} />
          </>
        ) : (
          <div className="p-3.5">
            {supplierHost && (
              <a
                href={supplierHost.startsWith('http') ? supplierHost : `https://${supplierHost}`}
                target="_blank"
                rel="noreferrer"
                className="mb-3 flex items-center justify-between gap-2 rounded-md border border-border bg-canvas px-3 py-2 text-[12.5px] text-ink transition-colors hover:border-accent-border hover:bg-accent-subtle hover:text-accent"
              >
                <span className="flex min-w-0 items-center gap-1.5">
                  <Globe size={13} className="shrink-0 text-ink-faint" />
                  <span className="truncate">{supplierHost}</span>
                </span>
                <ExternalLink size={12} className="shrink-0" />
              </a>
            )}
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
