import { AlertTriangle, ArrowLeft, Ban, Check, ChevronDown, Copy, ExternalLink, FolderSearch, Inbox, ListTodo, Loader2, Mail, MessageSquareText, MoreHorizontal, Package, PenSquare, Plus, RotateCw, Search, Send, Trash2, TrendingDown, TrendingUp, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { BulkComposeModal } from '../components/BulkComposeModal';
import { CopyButton } from '../components/ui/CopyButton';
import { DatePicker } from '../components/ui/DatePicker';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { checkoUrl, companyAge, formatCompanyName, formatMoney } from '../lib/format';
import { useReminders } from '../lib/RemindersContext';
import { formatTaskDeadline } from '../lib/taskSchedule';
import { requestStatusMeta, supplierMailStatusMeta } from '../lib/statusMeta';
import type { RequestSupplierRow, SupplierSendInput, Task } from '../lib/types';
import { useApiData } from '../lib/useApiData';

function toSendInput(s: RequestSupplierRow): SupplierSendInput {
  return { id: s.id, email: s.email, name: s.name, host: s.host, external_key: s.external_key, inn: s.inn, global_supplier_id: s.global_supplier_id };
}

type FilterKey = 'all' | 'answered' | 'waiting' | 'attention' | 'no_contact' | 'problem';

const FILTER_LABELS: Record<FilterKey, string> = {
  all: 'Все',
  answered: 'Есть ответ',
  waiting: 'Ждём ответа',
  attention: 'Требуют внимания',
  no_contact: 'Без контакта',
  problem: 'Ошибки',
};

// "Требуют внимания" reads unread_count -- already loaded on this row for
// every other purpose (the unread pill) -- rather than adding any new field
// or backend call; it is the one attention signal available here without
// touching needs_followup/contact-intelligence, which are explicitly out of
// scope for this reorganization.
function matchesFilter(s: RequestSupplierRow, filter: FilterKey): boolean {
  switch (filter) {
    case 'all':
      return true;
    case 'answered':
      return s.mail_status === 'answered';
    case 'waiting':
      return s.mail_status === 'waiting';
    case 'attention':
      return s.unread_count > 0;
    case 'no_contact':
      return s.email_count === 0;
    case 'problem':
      return s.mail_status === 'error' || s.mail_status === 'delivery_unknown';
    default:
      return true;
  }
}

export function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const requestId = Number(id);
  const navigate = useNavigate();
  const state = useApiData(() => api.getRequestDetail(requestId), [requestId]);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const [irrelevantId, setIrrelevantId] = useState<number | null>(null);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [tasksAddIntent, setTasksAddIntent] = useState(0);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [composeOpen, setComposeOpen] = useState(false);
  const [quickComposeId, setQuickComposeId] = useState<number | null>(null);
  const [copiedEmailValue, setCopiedEmailValue] = useState<'subject' | 'reference' | null>(null);
  const [emailCopyError, setEmailCopyError] = useState('');
  const mailAccountsState = useApiData(() => api.mailStatus(), []);
  const [sentPreview, setSentPreview] = useState<{ accountId: number; accountEmail: string; count: number }[] | null>(null);
  const [sentPreviewing, setSentPreviewing] = useState(false);
  const [sentImporting, setSentImporting] = useState(false);
  const [sentSyncMessage, setSentSyncMessage] = useState('');

  const suppliers = state.status === 'ready' ? state.data.items : [];
  const requestStatus = state.status === 'ready' ? state.data.request.status : undefined;
  const reload = state.reload;
  const { taskDataVersion } = useReminders();
  const tasksState = useApiData(() => api.listTasks().then((r) => r.items), [taskDataVersion]);
  const requestTasks = tasksState.status === 'ready' ? tasksState.data.filter((t) => t.request_id === requestId) : [];

  // A Vercel function may be recycled right after its response, so the search
  // (SERP -> crawl -> registry/INN resolution -> finance) is advanced one durable
  // step at a time while this page is open, instead of relying on a background
  // worker that only exists in local dev (python supplier_app.py's ThreadingHTTPServer).
  // Without this, a request started on production never gets past its first step:
  // suppliers show up without a resolved ИНН/registry/finance data, or don't show
  // up at all (a global "Поставщики" card is only created once ИНН resolves).
  useEffect(() => {
    if (requestStatus !== 'searching') return undefined;
    let cancelled = false;
    let busy = false;
    const tick = async () => {
      if (cancelled || busy) return;
      busy = true;
      try {
        await api.stepRequestSearch(requestId);
        if (!cancelled) reload();
      } catch {
        // Next tick retries transient network/function failures; a permanent
        // search error is persisted server-side and ends the loop via status.
      } finally {
        busy = false;
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [requestId, requestStatus, reload]);

  const counts = useMemo(() => {
    const c: Record<FilterKey, number> = { all: suppliers.length, answered: 0, waiting: 0, attention: 0, no_contact: 0, problem: 0 };
    for (const s of suppliers) {
      if (s.mail_status === 'answered') c.answered++;
      if (s.mail_status === 'waiting') c.waiting++;
      if (s.unread_count > 0) c.attention++;
      if (s.email_count === 0) c.no_contact++;
      if (s.mail_status === 'error' || s.mail_status === 'delivery_unknown') c.problem++;
    }
    return c;
  }, [suppliers]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return suppliers.filter((s) => {
      if (!matchesFilter(s, filter)) return false;
      if (!q) return true;
      const haystack = `${s.name} ${s.host} ${s.email} ${s.inn}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [suppliers, filter, query]);

  if (!id || Number.isNaN(requestId)) {
    return <EmptyState icon={Ban} title="Некорректный номер заявки" />;
  }
  if (state.status === 'loading') {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <PageHeader title="Заявка" />
        <LoadingState label="Загружаем заявку…" />
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className="flex h-full flex-col overflow-hidden">
        <PageHeader title="Заявка" />
        <ErrorState message={state.message} onRetry={state.reload} />
      </div>
    );
  }

  const { request, positions } = state.data;
  const statusMeta = requestStatusMeta[request.status];
  const externalEmailSubject = `[${request.email_reference}] ${request.name}`;

  async function copyEmailValue(value: string, kind: 'subject' | 'reference') {
    setEmailCopyError('');
    try {
      await navigator.clipboard.writeText(value);
      setCopiedEmailValue(kind);
      window.setTimeout(() => setCopiedEmailValue(null), 1800);
    } catch {
      setEmailCopyError('Не удалось скопировать. Выделите текст и скопируйте вручную.');
    }
  }

  async function previewRequestSentMail() {
    const accounts = mailAccountsState.status === 'ready'
      ? mailAccountsState.data.accounts.filter((account) => account.connected)
      : [];
    if (accounts.length === 0) {
      setSentSyncMessage('Подключите почтовый аккаунт в настройках, чтобы найти письмо.');
      return;
    }
    setSentPreviewing(true);
    setSentSyncMessage('');
    try {
      const previews = await Promise.all(accounts.map(async (account) => {
        const result = await api.mailSentPreview(account.id, requestId);
        return { accountId: account.id, accountEmail: account.email, count: result.marked_count };
      }));
      const found = previews.filter((item) => item.count > 0);
      setSentPreview(found);
      const count = found.reduce((total, item) => total + item.count, 0);
      setSentSyncMessage(count
        ? `Найдено ${count} писем с [${request.email_reference}]. Проверьте результат и импортируйте их в переписку.`
        : `В подключённых ящиках нет писем с [${request.email_reference}]. Личные письма с другими темами не читались.`);
    } catch (error) {
      setSentPreview(null);
      setSentSyncMessage(error instanceof ApiError ? error.message : 'Не удалось проверить «Отправленные».');
    } finally {
      setSentPreviewing(false);
    }
  }

  async function importRequestSentMail() {
    if (!sentPreview || sentPreview.length === 0) return;
    setSentImporting(true);
    setSentSyncMessage('');
    try {
      const results = await Promise.all(sentPreview.map((item) => api.mailSentSync(item.accountId, requestId)));
      const linked = results.reduce((total, item) => total + item.linked, 0);
      const history = results.reduce((total, item) => total + item.history_imported, 0);
      setSentPreview(null);
      setSentSyncMessage(`Импорт завершён: связано с заявкой — ${linked}, добавлено в переписку — ${history}.`);
    } catch (error) {
      setSentSyncMessage(error instanceof ApiError ? error.message : 'Не удалось импортировать найденные письма.');
    } finally {
      setSentImporting(false);
    }
  }

  async function retrySearch() {
    setRetrying(true);
    setRetryError('');
    try {
      await api.startRequestSearch(requestId);
      state.reload();
    } catch (e) {
      setRetryError(e instanceof ApiError ? e.message : 'Не удалось перезапустить поиск.');
    } finally {
      setRetrying(false);
    }
  }

  async function markIrrelevant(supplierId: number) {
    setIrrelevantId(supplierId);
    try {
      await api.markSupplierIrrelevant(requestId, supplierId);
      state.reload();
    } catch {
      // Silently keep the row -- the button staying enabled is feedback enough for a soft-fail here.
    } finally {
      setIrrelevantId(null);
    }
  }

  function openThread(supplierId: number) {
    navigate(`/messages?request=${requestId}&supplier=${supplierId}`);
  }

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setSelected((prev) => (visible.every((s) => prev.has(s.id)) ? new Set() : new Set(visible.map((s) => s.id))));
  }

  const selectedSuppliers = suppliers.filter((s) => selected.has(s.id) && s.email);
  const quickComposeSupplier = quickComposeId != null ? (suppliers.find((s) => s.id === quickComposeId) ?? null) : null;
  const composeRecipients = quickComposeSupplier ? [quickComposeSupplier] : selectedSuppliers;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex items-center gap-2 px-4 sm:px-6 pt-5">
        <Link to="/requests" className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink">
          <ArrowLeft size={13} />
          Заявки
        </Link>
      </div>

      <PageHeader
        title={request.name}
        description={`№${request.id} · ${statusMeta.label}${request.deadline ? ' · ' : ''}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <DeadlineTag deadline={request.deadline} />
            <Link to={`/messages?request=${requestId}`} className="flex h-8 items-center gap-1.5 rounded-md border border-border-strong px-2.5 text-[12px] font-medium text-ink-soft hover:bg-surface-hover">
              <MessageSquareText size={13} /> Переписка по заявке
            </Link>
            <div className="flex items-center rounded-md border border-border-strong">
              <button
                type="button"
                onClick={() => setTasksOpen((v) => !v)}
                aria-expanded={tasksOpen}
                className={`flex h-8 items-center gap-1.5 rounded-l-md border-r border-border-strong px-2.5 text-[12px] font-medium transition-colors ${tasksOpen ? 'bg-accent-subtle text-accent' : 'text-ink-soft hover:bg-surface-hover'}`}
              >
                <ListTodo size={13} /> Задачи <span className="tabular-nums opacity-80">{requestTasks.length}</span>
                <ChevronDown size={12} className={tasksOpen ? 'rotate-180' : ''} />
              </button>
              <button
                type="button"
                aria-label="Быстро создать задачу"
                title="Создать задачу"
                onClick={() => {
                  setTasksOpen(true);
                  setTasksAddIntent((v) => v + 1);
                }}
                className="flex h-8 w-8 items-center justify-center rounded-r-md text-ink-soft hover:bg-surface-hover"
              >
                <Plus size={13} />
              </button>
            </div>
            {(request.status === 'error' || request.status === 'completed') && (
              <Button variant="secondary" size="sm" icon={<RotateCw size={13} />} disabled={retrying} onClick={() => void retrySearch()}>
                {retrying ? 'Запускаем…' : 'Перезапустить поиск'}
              </Button>
            )}
          </div>
        }
      />

      {retryError && <p className="px-4 sm:px-6 pb-2 text-[12px] text-danger">{retryError}</p>}

      {request.description && <p className="px-4 sm:px-6 pb-2 line-clamp-1 text-[12.5px] text-ink-soft" title={request.description}>{request.description}</p>}

      {tasksOpen && (
        <TasksOnRequest requestId={requestId} tasks={requestTasks} loading={tasksState.status === 'loading'} onReload={tasksState.reload} addIntent={tasksAddIntent} />
      )}

      {/* Mail identifier: a single compact utility row instead of a full-width
       * card. The two copy actions are visually distinct (labeled) rather
       * than two identical unlabeled icons, and "Найти в «Отправленных»" is
       * a real bordered button so it doesn't blend into the row. */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border px-4 sm:px-6 py-2 text-[12px]">
        <Mail size={13} className="shrink-0 text-ink-faint" aria-hidden="true" />
        <span
          className="rounded bg-accent-subtle px-1.5 py-0.5 font-mono text-[11px] font-semibold text-accent"
          title="Вставьте тему в Gmail, Яндекс.Почту или корпоративный клиент — ID поможет найти переписку после синхронизации."
        >
          {request.email_reference}
        </span>
        <button type="button" aria-label="Скопировать тему письма" onClick={() => void copyEmailValue(externalEmailSubject, 'subject')} className="flex h-6 items-center gap-1 rounded-md px-1.5 text-[11.5px] text-ink-muted hover:bg-surface-hover hover:text-ink">
          {copiedEmailValue === 'subject' ? <Check size={12} className="text-success" /> : <Copy size={12} />} Тема
        </button>
        <button type="button" aria-label="Скопировать ID заявки" onClick={() => void copyEmailValue(request.email_reference, 'reference')} className="flex h-6 items-center gap-1 rounded-md px-1.5 text-[11.5px] text-ink-muted hover:bg-surface-hover hover:text-ink">
          {copiedEmailValue === 'reference' ? <Check size={12} className="text-success" /> : <Copy size={12} />} ID
        </button>
        {sentPreview && sentPreview.length > 0 ? (
          <Button variant="primary" size="sm" icon={sentImporting ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} disabled={sentImporting} onClick={() => void importRequestSentMail()}>
            Импортировать ({sentPreview.reduce((total, item) => total + item.count, 0)})
          </Button>
        ) : (
          <button type="button" disabled={sentPreviewing || sentImporting} onClick={() => void previewRequestSentMail()} className="flex h-7 items-center gap-1 rounded-md border border-border-strong px-2 text-[11.5px] font-medium text-ink-soft hover:bg-surface-hover disabled:opacity-50">
            {sentPreviewing ? <Loader2 size={12} className="animate-spin" /> : <FolderSearch size={12} />} Найти в «Отправленных»
          </button>
        )}
        {(emailCopyError || sentSyncMessage) && <p aria-live="polite" className="basis-full text-[11px] text-ink-muted">{emailCopyError || sentSyncMessage}</p>}
      </div>

      {positions.length > 0 && <PositionsRow positions={positions} />}

      {/* One row: the filter pills ARE the summary (each carries its own
       * count) -- a separate read-only badge row above this repeated the
       * exact same numbers under different labels ("Ответили 24" next to
       * "Есть ответ"), which is exactly the duplication being removed here. */}
      <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 sm:px-6 py-2">
        <div className="flex flex-wrap gap-1.5">
          {(Object.keys(FILTER_LABELS) as FilterKey[])
            .filter((key) => key === 'all' || counts[key] > 0)
            .map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setFilter(key)}
                className={
                  filter === key
                    ? 'rounded-md bg-accent px-2.5 py-1 text-[11.5px] font-medium text-white'
                    : 'rounded-md border border-border-strong px-2.5 py-1 text-[11.5px] text-ink-soft hover:bg-surface-hover'
                }
              >
                {FILTER_LABELS[key]} <span className="tabular-nums opacity-70">{counts[key]}</span>
              </button>
            ))}
        </div>
        {selectedSuppliers.length > 0 && (
          <Button variant="primary" size="sm" icon={<PenSquare size={13} />} onClick={() => setComposeOpen(true)}>
            Написать ({selectedSuppliers.length})
          </Button>
        )}
        <div className="relative ml-auto w-[240px]">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск: компания, сайт, ИНН…"
            className="h-8 w-full rounded-md border border-border-strong bg-surface pl-7 pr-2.5 text-[12px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>
      </div>

      {(composeOpen || quickComposeSupplier) && (
        <BulkComposeModal
          requestId={requestId}
          recipients={composeRecipients.map(toSendInput)}
          onClose={() => {
            setComposeOpen(false);
            setQuickComposeId(null);
          }}
          onSent={() => {
            setSelected(new Set());
            setQuickComposeId(null);
            state.reload();
          }}
        />
      )}

      <div className="min-w-0 flex-1 overflow-auto border-t border-border">
        {suppliers.length === 0 ? (
          <EmptyState icon={Inbox} title="Поставщики ещё не найдены" description="Запустите поиск, чтобы система нашла кандидатов." />
        ) : visible.length === 0 ? (
          <EmptyState icon={Search} title="Ничего не найдено" description="Попробуйте другой фильтр или запрос." />
        ) : (
          <>
          <div className="flex flex-col divide-y divide-border sm:hidden">
            {visible.map((s) => (
              <SupplierMobileRow
                key={s.id}
                s={s}
                selected={selected.has(s.id)}
                onToggleSelected={() => toggleSelected(s.id)}
                onCompose={() => setQuickComposeId(s.id)}
                onOpenThread={() => openThread(s.id)}
                onMarkIrrelevant={() => void markIrrelevant(s.id)}
                markingIrrelevant={irrelevantId === s.id}
              />
            ))}
          </div>
          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full table-fixed border-collapse text-[12.5px]">
              <colgroup>
                <col className="w-9" />
                <col className="w-[19%]" />
                <col className="w-[15%]" />
                <col className="w-[7%]" />
                <col className="w-[9%]" />
                <col className="w-[9%]" />
                <col className="w-[10%]" />
                <col className="w-[13%]" />
                <col className="w-[150px]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-canvas">
                <tr className="border-b border-border">
                  <th className="px-3 py-2 pl-6">
                    <input
                      type="checkbox"
                      checked={visible.length > 0 && visible.every((s) => selected.has(s.id))}
                      onChange={toggleSelectAllVisible}
                      aria-label="Выбрать всех"
                      className="h-3.5 w-3.5 rounded border-border-strong accent-accent"
                    />
                  </th>
                  {['Компания', 'Контакт', 'Возраст', 'Выручка', 'Прибыль', 'ЕГРЮЛ', 'Коммуникация', ''].map((h) => (
                    <th key={h} className="truncate px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-muted last:pr-6">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((s) => (
                  <SupplierTableRow
                    key={s.id}
                    s={s}
                    selected={selected.has(s.id)}
                    onToggleSelected={() => toggleSelected(s.id)}
                    onCompose={() => setQuickComposeId(s.id)}
                    onOpenThread={() => openThread(s.id)}
                    onMarkIrrelevant={() => void markIrrelevant(s.id)}
                    markingIrrelevant={irrelevantId === s.id}
                  />
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </div>
    </div>
  );
}

/** "Позиции · N" — business content, not technical metadata: same visual
 * weight as the other section headers, collapsing past 6 items instead of
 * an always-fully-expanded chip row. */
function PositionsRow({ positions }: { positions: { position_key: string; name: string; quantity: string }[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? positions : positions.slice(0, 6);
  const hiddenCount = positions.length - visible.length;
  return (
    <div className="border-t border-border px-4 sm:px-6 py-2">
      <div className="mb-1 flex items-center gap-1.5 text-[12px] font-semibold text-ink">
        <Package size={13} className="text-ink-muted" />
        Позиции · {positions.length}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {visible.map((p) => (
          <span key={p.position_key} className="rounded-md border border-border-strong bg-surface px-2.5 py-1 text-[12px] text-ink-soft">
            {p.name}
            {p.quantity ? <span className="text-ink-faint"> · {p.quantity}</span> : null}
          </span>
        ))}
        {hiddenCount > 0 && (
          <button type="button" onClick={() => setExpanded(true)} className="text-[11.5px] font-medium text-accent hover:text-accent-hover">
            +{hiddenCount} ещё
          </button>
        )}
        {expanded && positions.length > 6 && (
          <button type="button" onClick={() => setExpanded(false)} className="text-[11.5px] text-ink-faint hover:text-ink">
            Свернуть
          </button>
        )}
      </div>
    </div>
  );
}

/** Communication cell: the state itself explains the situation (§8) instead
 * of a bare badge -- an unread reply is called out as needing attention, and
 * a delivery problem shows its actual error, not just a generic label. */
function CommunicationCell({ s }: { s: RequestSupplierRow }) {
  const mailMeta = supplierMailStatusMeta[s.mail_status] ?? supplierMailStatusMeta.not_sent;
  const isProblem = s.mail_status === 'error' || s.mail_status === 'delivery_unknown';
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <div className="flex items-center gap-1.5">
        <Badge tone={mailMeta.tone}>{mailMeta.label}</Badge>
        {s.unread_count > 0 && (
          <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">{s.unread_count}</span>
        )}
      </div>
      {s.unread_count > 0 && (
        <span className="flex items-center gap-1 text-[10.5px] font-medium text-accent">
          <AlertTriangle size={10} /> Требует внимания
        </span>
      )}
      {isProblem && s.last_error && (
        <p className="truncate text-[10.5px] text-danger" title={s.last_error}>{s.last_error}</p>
      )}
    </div>
  );
}

/** One primary action instead of a row of equally-weighted icons (§9):
 * an unread reply or an existing conversation both open the thread, an
 * unsent contact gets "Написать", and no email at all is a plain state, not
 * an invented "find contact" flow that doesn't exist elsewhere in the app. */
function PrimaryAction({
  s, onCompose, onOpenThread,
}: { s: RequestSupplierRow; onCompose: () => void; onOpenThread: () => void }) {
  if (!s.email) return <span className="text-[11.5px] text-ink-faint">Нет контакта</span>;
  if (s.mail_status === 'not_sent') {
    return <Button variant="primary" size="sm" icon={<Send size={12} />} onClick={onCompose}>Написать</Button>;
  }
  return <Button variant="secondary" size="sm" icon={<MessageSquareText size={12} />} onClick={onOpenThread}>{s.unread_count > 0 ? 'Открыть переписку' : 'Переписка'}</Button>;
}

/** Secondary action ("не подходит") behind a native <details> disclosure --
 * no extra open/close state, closes on outside click/Escape for free. The
 * Checko profile link lives inline in the ЕГРЮЛ cell (matching Suppliers.tsx),
 * not hidden in here. */
function OverflowMenu({ onMarkIrrelevant, markingIrrelevant }: { onMarkIrrelevant: () => void; markingIrrelevant: boolean }) {
  return (
    <details className="relative">
      <summary aria-label="Ещё действия" className="flex h-7 w-7 cursor-pointer list-none items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover hover:text-ink [&::-webkit-details-marker]:hidden">
        <MoreHorizontal size={15} />
      </summary>
      <div className="absolute right-0 top-8 z-20 w-44 rounded-md border border-border bg-surface py-1 shadow-lg">
        <button
          type="button"
          disabled={markingIrrelevant}
          onClick={onMarkIrrelevant}
          className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12px] text-danger hover:bg-danger-subtle disabled:opacity-50"
        >
          <Ban size={13} /> Не подходит
        </button>
      </div>
    </details>
  );
}

function CompanyCell({ s }: { s: RequestSupplierRow }) {
  const site = s.host ? (s.host.startsWith('http') ? s.host : `https://${s.host}`) : null;
  return (
    <div className="min-w-0">
      {s.global_supplier_id ? (
        <Link to={`/suppliers/${s.global_supplier_id}`} onClick={(e) => e.stopPropagation()} className="truncate font-medium text-ink hover:text-accent hover:underline">
          {formatCompanyName(s.name)}
        </Link>
      ) : (
        <p className="truncate font-medium text-ink" title="Карточка появится после подтверждения ИНН">{formatCompanyName(s.name)}</p>
      )}
      <p className="truncate text-[11px] text-ink-muted">
        {s.inn && `ИНН ${s.inn}`}{s.inn && s.region ? ' · ' : ''}{s.region}
      </p>
      {site && (
        <a href={site} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="inline-flex items-center gap-0.5 truncate text-[11px] text-accent hover:underline">
          {s.host} <ExternalLink size={9} />
        </a>
      )}
    </div>
  );
}

/** Finance/legal cells matching Suppliers.tsx's own Checko-derived display
 * exactly (bold revenue, colored profit with a trend icon, ЕГРЮЛ status with
 * the Checko profile link inline) -- restored per the owner's explicit
 * request to keep this identical between the two screens. */
function AgeCell({ s }: { s: RequestSupplierRow }) {
  return <span className="text-ink-soft">{companyAge(s.registry?.registered_at) ?? '—'}</span>;
}

function RevenueCell({ s }: { s: RequestSupplierRow }) {
  if (s.finances?.revenue == null) return <span className="text-ink-faint">—</span>;
  return (
    <>
      <p className="whitespace-nowrap font-semibold text-ink">{formatMoney(s.finances.revenue)}</p>
      {s.finances.report_year && <p className="text-[10.5px] text-ink-faint">за {s.finances.report_year}</p>}
    </>
  );
}

function ProfitCell({ s }: { s: RequestSupplierRow }) {
  const profit = s.finances?.profit ?? null;
  if (profit == null) return <span className="text-ink-faint">—</span>;
  return (
    <span className={`flex whitespace-nowrap items-center gap-1 font-semibold ${profit >= 0 ? 'text-success' : 'text-danger'}`}>
      {profit >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
      {formatMoney(profit)}
    </span>
  );
}

function RegistryCell({ s }: { s: RequestSupplierRow }) {
  const checko = checkoUrl(s.registry?.ogrn);
  return (
    <div className="flex items-center gap-1.5">
      {s.registry ? (
        <span className={s.registry.is_active === false ? 'truncate text-danger' : 'truncate text-success'}>
          {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
        </span>
      ) : (
        <span className="text-ink-faint">—</span>
      )}
      {checko && (
        <a href={checko} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="Профиль на Checko" className="flex h-6 w-6 items-center justify-center rounded-md hover:bg-surface-hover">
          <img src={checkoIcon} alt="Checko" className="h-3.5 w-3.5" />
        </a>
      )}
    </div>
  );
}

function SupplierTableRow({
  s, selected, onToggleSelected, onCompose, onOpenThread, onMarkIrrelevant, markingIrrelevant,
}: {
  s: RequestSupplierRow; selected: boolean; onToggleSelected: () => void; onCompose: () => void;
  onOpenThread: () => void; onMarkIrrelevant: () => void; markingIrrelevant: boolean;
}) {
  return (
    <tr className={`border-b border-border last:border-0 hover:bg-surface-hover ${selected ? 'bg-accent-subtle/30' : ''}`}>
      <td className="px-3 py-2.5 pl-6 align-middle">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggleSelected}
          disabled={!s.email}
          title={s.email ? undefined : 'Нет email — нельзя выбрать для рассылки'}
          aria-label={`Выбрать ${s.name}`}
          className="h-3.5 w-3.5 rounded border-border-strong accent-accent disabled:opacity-30"
        />
      </td>
      <td className="px-3 py-2.5 align-middle"><CompanyCell s={s} /></td>
      <td className="px-3 py-2.5 align-middle text-ink-soft">
        {s.email ? (
          <div className="flex min-w-0 items-center gap-1"><span className="min-w-0 truncate">{s.email}</span><CopyButton text={s.email} /></div>
        ) : (
          <span className="text-[11.5px] text-ink-faint">Нет email</span>
        )}
      </td>
      <td className="px-3 py-2.5 align-middle"><AgeCell s={s} /></td>
      <td className="px-3 py-2.5 align-middle"><RevenueCell s={s} /></td>
      <td className="px-3 py-2.5 align-middle"><ProfitCell s={s} /></td>
      <td className="px-3 py-2.5 align-middle"><RegistryCell s={s} /></td>
      <td className="px-3 py-2.5 align-middle"><CommunicationCell s={s} /></td>
      <td className="px-3 py-2.5 pr-6 align-middle">
        <div className="flex items-center justify-end gap-1">
          <PrimaryAction s={s} onCompose={onCompose} onOpenThread={onOpenThread} />
          <OverflowMenu onMarkIrrelevant={onMarkIrrelevant} markingIrrelevant={markingIrrelevant} />
        </div>
      </td>
    </tr>
  );
}

function SupplierMobileRow({
  s, selected, onToggleSelected, onCompose, onOpenThread, onMarkIrrelevant, markingIrrelevant,
}: {
  s: RequestSupplierRow; selected: boolean; onToggleSelected: () => void; onCompose: () => void;
  onOpenThread: () => void; onMarkIrrelevant: () => void; markingIrrelevant: boolean;
}) {
  return (
    <div className={`flex flex-col gap-2 px-4 py-3 ${selected ? 'bg-accent-subtle/30' : ''}`}>
      <div className="flex items-center gap-2.5">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggleSelected}
          disabled={!s.email}
          aria-label={`Выбрать ${s.name}`}
          className="h-3.5 w-3.5 shrink-0 rounded border-border-strong accent-accent disabled:opacity-30"
        />
        <div className="min-w-0 flex-1">
          <CompanyCell s={s} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pl-6 text-[11.5px]">
        <RevenueCell s={s} />
        <ProfitCell s={s} />
        <AgeCell s={s} />
        <RegistryCell s={s} />
      </div>
      <div className="pl-6"><CommunicationCell s={s} /></div>
      <div className="flex items-center justify-end gap-1.5">
        <PrimaryAction s={s} onCompose={onCompose} onOpenThread={onOpenThread} />
        <OverflowMenu onMarkIrrelevant={onMarkIrrelevant} markingIrrelevant={markingIrrelevant} />
      </div>
    </div>
  );
}

/** Compact task list for a specific request — shown above the suppliers table. */
/** Only rendered while the header's "Задачи · N" toggle is open (§4) --
 * never sits between filters and the supplier table, and never renders an
 * empty box when collapsed. */
function TasksOnRequest({
  requestId, tasks, loading, onReload, addIntent,
}: { requestId: number; tasks: Task[]; loading: boolean; onReload: () => void; addIntent: number }) {
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);
  const suppliersState = useApiData(() => api.listGlobalSuppliers().then((r) => r.items), []);
  const [adding, setAdding] = useState(false);
  useEffect(() => {
    if (addIntent > 0) setAdding(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addIntent]);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [createError, setCreateError] = useState('');

  const suppliers = suppliersState.status === 'ready' ? suppliersState.data : [];

  async function add() {
    if (!title.trim()) return;
    setSubmitting(true);
    setCreateError('');
    try {
      await api.createTask({ title: title.trim(), due_date: dueDate || undefined, request_id: requestId, supplier_id: selectedSupplierId || undefined });
      setTitle('');
      setDueDate('');
      setSelectedSupplierId(null);
      setAdding(false);
      onReload();
    } catch {
      setCreateError('Не удалось создать задачу.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="border-t border-border bg-canvas/40">
      <div className="flex items-center justify-between px-4 sm:px-6 py-2">
        <h3 className="text-[11.5px] font-semibold uppercase tracking-wide text-ink-faint">Задачи по заявке</h3>
        <Button variant="ghost" size="sm" icon={<Plus size={13} />} onClick={() => setAdding((v) => !v)}>Задача</Button>
      </div>

      {adding && (
        <div className="flex flex-wrap items-center gap-1.5 border-t border-border px-4 sm:px-6 py-2.5">
          <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && void add()} placeholder="Текст задачи…" className="h-8 min-w-0 flex-1 rounded-md border border-border-strong bg-canvas px-2.5 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
          <DatePicker value={dueDate} onChange={setDueDate} className="w-[150px]" />
          <select aria-label="Привязать поставщика" value={selectedSupplierId ?? ''} onChange={(e) => setSelectedSupplierId(e.target.value ? Number(e.target.value) : null)} className="h-8 min-w-0 rounded-md border border-border-strong bg-surface px-2 text-[12px] text-ink outline-none focus:border-accent focus:ring-1 focus:ring-accent-border">
            <option value="">Без поставщика</option>
            {suppliers.slice(0, 50).map((s) => <option key={s.id} value={s.id}>{formatCompanyName(s.name)}</option>)}
          </select>
          <Button variant="primary" size="sm" disabled={!title.trim() || submitting} onClick={() => void add()}>Добавить</Button>
          <button type="button" onClick={() => setAdding(false)} aria-label="Отменить" className="flex h-8 w-8 items-center justify-center rounded-md text-ink-faint hover:bg-surface-hover"><X size={14} /></button>
          {createError && <p className="basis-full text-[11.5px] text-danger">{createError}</p>}
        </div>
      )}

      {loading ? (
        <LoadingState label="Загружаем задачи…" />
      ) : tasks.length > 0 ? (
        <div className="flex flex-col divide-y divide-border border-t border-border">
          {tasks.map((t) => (
            <div key={t.id} className="flex items-center gap-2.5 px-4 sm:px-6 py-2 hover:bg-surface-hover">
              <CheckboxCircle
                checked={t.done}
                onChange={async () => {
                  setBusyId(t.id);
                  try { await api.setTaskDone(t.id, !t.done); onReload(); } finally { setBusyId(null); }
                }}
                disabled={busyId === t.id}
              />
              <div className="min-w-0 flex-1">
                <Link to={`/?task=${t.id}`} className={`truncate text-[12.5px] ${t.done ? 'text-ink-faint line-through' : 'text-ink'} hover:text-accent`}>{t.title}</Link>
                {t.due_date && <p className="text-[11px] text-ink-faint">{formatTaskDeadline(t)}</p>}
                {t.supplier_id && t.supplier_name && <p className="truncate text-[11px] text-accent">{formatCompanyName(t.supplier_name)}</p>}
              </div>
              <button type="button" disabled={busyId === t.id} onClick={async () => { setBusyId(t.id); try { await api.deleteTask(t.id); onReload(); } finally { setBusyId(null); } }} aria-label="Удалить" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-danger-subtle hover:text-danger"><Trash2 size={12} /></button>
            </div>
          ))}
        </div>
      ) : (
        !adding && <p className="border-t border-border px-4 sm:px-6 py-2.5 text-[11.5px] text-ink-faint">Нет задач по этой заявке.</p>
      )}
    </section>
  );
}

function CheckboxCircle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled: boolean }) {
  return (
    <button type="button" disabled={disabled} onClick={onChange} aria-label={checked ? 'Отменить выполнение' : 'Отметить выполненной'} className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors ${checked ? 'border-accent bg-accent text-white' : 'border-border-strong text-transparent hover:border-accent'} disabled:opacity-40`}>
      {checked && <Check size={10} />}
    </button>
  );
}
