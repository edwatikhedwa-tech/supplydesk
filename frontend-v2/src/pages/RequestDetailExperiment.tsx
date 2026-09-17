import { ArrowLeft, Ban, Check, ChevronDown, ChevronUp, Copy, ExternalLink, FolderSearch, Inbox, ListTodo, Loader2, Mail, MessageSquareText, Package, Plus, RotateCw, Search, Send, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { BulkComposeModal } from '../components/BulkComposeModal';
import { CopyButton } from '../components/ui/CopyButton';
import { DatePicker } from '../components/ui/DatePicker';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { checkoUrl, companyAge, formatCompanyName, formatMoney } from '../lib/format';
import { formatTaskDeadline } from '../lib/taskSchedule';
import { requestStatusMeta } from '../lib/statusMeta';
import type { RequestSupplierRow, SupplierSendInput } from '../lib/types';
import { useApiData } from '../lib/useApiData';

function toSendInput(s: RequestSupplierRow): SupplierSendInput {
  return { id: s.id, email: s.email, name: s.name, host: s.host, external_key: s.external_key, inn: s.inn, global_supplier_id: s.global_supplier_id };
}

type FilterKey = 'all' | 'answered' | 'waiting' | 'attention' | 'no_contact' | 'error';

const FILTER_DEFS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'answered', label: 'Есть ответ' },
  { key: 'waiting', label: 'Ждём ответа' },
  { key: 'attention', label: 'Требуют внимания' },
  { key: 'no_contact', label: 'Без контакта' },
  { key: 'error', label: 'Ошибки' },
];

function matchesFilter(s: RequestSupplierRow, filter: FilterKey): boolean {
  switch (filter) {
    case 'all': return true;
    case 'answered': return s.mail_status === 'answered';
    case 'waiting': return s.mail_status === 'waiting';
    case 'attention': return (s.mail_status === 'sent' || s.mail_status === 'waiting') && !s.unread_count;
    case 'no_contact': return s.email_count === 0;
    case 'error': return s.mail_status === 'error' || s.mail_status === 'delivery_unknown';
    default: return true;
  }
}

function statusContext(s: RequestSupplierRow): { label: string; tone: 'danger' | 'warning' | 'success' | 'neutral' | 'accent'; detail?: string } {
  switch (s.mail_status) {
    case 'not_sent':
      return s.email ? { label: 'Не отправлено', tone: 'neutral', detail: 'Написать' } : { label: 'Нет контакта', tone: 'neutral' };
    case 'sent': return { label: 'Отправлено', tone: 'neutral' };
    case 'waiting': return { label: 'Ждём ответа', tone: 'warning' };
    case 'answered': return { label: 'Есть ответ', tone: 'success' };
    case 'error': return { label: 'Ошибка', tone: 'danger', detail: s.last_error || 'Send failed' };
    case 'delivery_unknown': return { label: 'Статус неизвестен', tone: 'neutral' };
    default: return { label: s.mail_status, tone: 'neutral' };
  }
}

function primaryActionFor(s: RequestSupplierRow): 'compose' | 'thread' | 'add_contact' | 'none' {
  if (!s.email) return 'add_contact';
  if (s.mail_status === 'answered') return 'thread';
  if (s.mail_status === 'not_sent') return 'compose';
  return 'thread';
}

/** ── EXPERIMENTAL REQUEST DETAIL PAGE ── */
export function RequestDetailExperiment() {
  const { id } = useParams<{ id: string }>();
  const requestId = Number(id);
  const navigate = useNavigate();
  const state = useApiData(() => api.getRequestDetail(requestId), [requestId]);
  const tasksState = useApiData(() => api.listTasks().then((r) => r.items), []);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');
  const [irrelevantId, setIrrelevantId] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [composeOpen, setComposeOpen] = useState(false);
  const [quickComposeId, setQuickComposeId] = useState<number | null>(null);
  const [copiedEmailValue, setCopiedEmailValue] = useState<'subject' | 'reference' | null>(null);
  const [sentSyncMessage, setSentSyncMessage] = useState('');
  const mailAccountsState = useApiData(() => api.mailStatus(), []);
  const [sentPreview, setSentPreview] = useState<{ accountId: number; accountEmail: string; count: number }[] | null>(null);
  const [sentPreviewing, setSentPreviewing] = useState(false);
  const [sentImporting, setSentImporting] = useState(false);

  // Tasks
  const [tasksOpen, setTasksOpen] = useState(false);
  const [addingTask, setAddingTask] = useState(false);
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDueDate, setTaskDueDate] = useState('');
  const [taskSelectedSupplierId, setTaskSelectedSupplierId] = useState<number | null>(null);
  const [taskSubmitting, setTaskSubmitting] = useState(false);
  const [taskBusyId, setTaskBusyId] = useState<number | null>(null);
  const availableSuppliers = useApiData(() => api.listGlobalSuppliers().then((r) => r.items), []);
  const [positionsExpanded, setPositionsExpanded] = useState(false);

  const suppliers = state.status === 'ready' ? state.data.items : [];
  const requestStatus = state.status === 'ready' ? state.data.request.status : undefined;
  const reload = state.reload;
  const tasks = tasksState.status === 'ready' ? tasksState.data.filter((t) => t.request_id === requestId) : [];

  useEffect(() => {
    if (requestStatus !== 'searching') return undefined;
    let cancelled = false;
    let busy = false;
    const tick = async () => {
      if (cancelled || busy) return;
      busy = true;
      try { await api.stepRequestSearch(requestId); if (!cancelled) reload(); } catch { /* retry */ } finally { busy = false; }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 1500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [requestId, requestStatus, reload]);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: suppliers.length, answered: 0, waiting: 0, attention: 0, no_contact: 0, error: 0 };
    for (const s of suppliers) {
      if (s.mail_status === 'answered') c.answered++;
      else if (s.mail_status === 'waiting' || s.mail_status === 'sent') c.waiting++;
      if (!s.email || s.email_count === 0) c.no_contact++;
      if (s.mail_status === 'error' || s.mail_status === 'delivery_unknown') c.error++;
    }
    c.attention = suppliers.filter((s) => s.mail_status === 'waiting' || s.mail_status === 'sent').length;
    return c;
  }, [suppliers]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return suppliers.filter((s) => {
      if (!matchesFilter(s, filter)) return false;
      if (!q) return true;
      return `${s.name} ${s.host} ${s.email} ${s.inn}`.toLowerCase().includes(q);
    });
  }, [suppliers, filter, query]);

  const metrics = state.status === 'ready' ? state.data.request.mail_metrics : undefined;

  if (!id || Number.isNaN(requestId)) return <EmptyState icon={Ban} title="Некорректный номер заявки" />;
  if (state.status === 'loading') return <div className="flex h-full flex-col overflow-hidden"><LoadingState label="Загружаем заявку…" /></div>;
  if (state.status === 'error') return <div className="flex h-full flex-col overflow-hidden"><ErrorState message={state.message} onRetry={state.reload} /></div>;

  const { request, positions } = state.data;
  const statusMeta = requestStatusMeta[request.status];
  const selectedSuppliers = suppliers.filter((s) => selected.has(s.id) && s.email);
  const quickComposeSupplier = quickComposeId != null ? (suppliers.find((s) => s.id === quickComposeId) ?? null) : null;
  const composeRecipients = quickComposeSupplier ? [quickComposeSupplier] : selectedSuppliers;
  const supplierMasters = availableSuppliers.status === 'ready' ? availableSuppliers.data : [];

  async function copyEmailValue(value: string, kind: 'subject' | 'reference') {
    try { await navigator.clipboard.writeText(value); setCopiedEmailValue(kind); window.setTimeout(() => setCopiedEmailValue(null), 1800); } catch { /* silent */ }
  }

  async function previewSentMail() {
    const accounts = mailAccountsState.status === 'ready' ? mailAccountsState.data.accounts.filter((a) => a.connected) : [];
    if (!accounts.length) { setSentSyncMessage('Подключите почтовый аккаунт.'); return; }
    setSentPreviewing(true);
    setSentSyncMessage('');
    try {
      const previews = await Promise.all(accounts.map(async (a) => {
        const r = await api.mailSentPreview(a.id, requestId);
        return { accountId: a.id, accountEmail: a.email, count: r.marked_count };
      }));
      const found = previews.filter((item) => item.count > 0);
      setSentPreview(found);
      setSentSyncMessage(found.reduce((s, item) => s + item.count, 0) ? `Найдено писем.` : `Нет писем с [${request.email_reference}].`);
    } catch (e) { setSentSyncMessage(e instanceof ApiError ? e.message : 'Ошибка проверки.'); } finally { setSentPreviewing(false); }
  }

  async function importSentMail() {
    if (!sentPreview?.length) return;
    setSentImporting(true);
    try {
      const results = await Promise.all(sentPreview.map((item) => api.mailSentSync(item.accountId, requestId)));
      const linked = results.reduce((s, r) => s + r.linked, 0);
      const history = results.reduce((s, r) => s + r.history_imported, 0);
      setSentPreview(null);
      setSentSyncMessage(`Импорт: связано ${linked}, добавлено ${history}.`);
    } catch (e) { setSentSyncMessage(e instanceof ApiError ? e.message : 'Ошибка импорта.'); } finally { setSentImporting(false); }
  }

  async function retrySearch() {
    setRetrying(true); setRetryError('');
    try { await api.startRequestSearch(requestId); reload(); } catch (e) { setRetryError(e instanceof ApiError ? e.message : 'Ошибка.'); } finally { setRetrying(false); }
  }

  async function markIrrelevant(supplierId: number) {
    setIrrelevantId(supplierId);
    try { await api.markSupplierIrrelevant(requestId, supplierId); reload(); } catch { /* silent */ } finally { setIrrelevantId(null); }
  }

  function openThread(supplierId: number) { navigate(`/messages?request=${requestId}&supplier=${supplierId}`); }
  function toggleSelected(supplierId: number) { setSelected((prev) => { const n = new Set(prev); if (n.has(supplierId)) n.delete(supplierId); else n.add(supplierId); return n; }); }
  function toggleSelectAll() { setSelected((prev) => (visible.every((s) => prev.has(s.id)) ? new Set() : new Set(visible.map((s) => s.id)))); }

  async function addTask() {
    if (!taskTitle.trim()) return;
    setTaskSubmitting(true);
    try {
      await api.createTask({ title: taskTitle.trim(), due_date: taskDueDate || undefined, request_id: requestId, supplier_id: taskSelectedSupplierId || undefined });
      setTaskTitle(''); setTaskDueDate(''); setTaskSelectedSupplierId(null); setAddingTask(false); tasksState.reload();
    } catch { /* silent */ } finally { setTaskSubmitting(false); }
  }

  const externalEmailSubject = `[${request.email_reference}] ${request.name}`;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ← Back */}
      <div className="flex items-center gap-2 px-4 sm:px-6 pt-3">
        <Link to="/requests" className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink">
          <ArrowLeft size={13} /> Заявки
        </Link>
      </div>

      {/* Header row */}
      <div className="flex items-start justify-between gap-4 px-4 sm:px-6 pt-2 pb-1">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[18px] font-display font-semibold text-ink">{request.name}</h1>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12px] text-ink-muted">
            <span>№{request.id}</span>
            <Badge tone={statusMeta.tone}>{statusMeta.label}</Badge>
            <DeadlineTag deadline={request.deadline} />
            <span>{request.sender_name}</span>
            {request.company_name && <span>· {request.company_name}</span>}
          </p>
          {request.description && <p className="mt-0.5 text-[12px] text-ink-soft">{request.description}</p>}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          <button type="button" onClick={() => { setTasksOpen((v) => !v); if (!tasksOpen) setAddingTask(false); }}
            className={`flex h-7 items-center gap-1 rounded-md border px-2 text-[12px] font-medium transition-colors ${tasksOpen ? 'border-accent-border bg-accent-subtle text-accent' : 'border-border-strong text-ink-muted hover:bg-surface-hover'}`}>
            <ListTodo size={13} /> {tasks.length}
          </button>
          {(request.status === 'error' || request.status === 'completed') && (
            <Button variant="ghost" size="sm" icon={<RotateCw size={13} />} disabled={retrying} onClick={() => void retrySearch()}>
              {retrying ? '…' : 'Поиск'}
            </Button>
          )}
        </div>
      </div>

      {retryError && <p className="px-4 sm:px-6 pb-1 text-[12px] text-danger">{retryError}</p>}

      {/* Tasks (collapsible) */}
      {tasksOpen && (
        <div className="border-b border-border px-4 sm:px-6 py-2">
          {addingTask ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <input autoFocus value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && void addTask()}
                placeholder="Текст задачи…" className="h-7 min-w-0 flex-1 rounded border border-border-strong bg-canvas px-2 text-[12px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
              <DatePicker value={taskDueDate} onChange={setTaskDueDate} className="w-[130px]" />
              <select value={taskSelectedSupplierId ?? ''} onChange={(e) => setTaskSelectedSupplierId(e.target.value ? Number(e.target.value) : null)}
                className="h-7 min-w-0 rounded border border-border-strong bg-surface px-2 text-[11.5px] outline-none focus:border-accent">
                <option value="">Без поставщика</option>
                {supplierMasters.slice(0, 50).map((s) => <option key={s.id} value={s.id}>{formatCompanyName(s.name)}</option>)}
              </select>
              <button type="button" disabled={!taskTitle.trim() || taskSubmitting} onClick={() => void addTask()}
                className="h-7 rounded bg-accent px-2.5 text-[11.5px] font-medium text-white hover:bg-accent-hover disabled:opacity-60">Добавить</button>
              <button type="button" onClick={() => setAddingTask(false)} aria-label="Отмена" className="flex h-7 w-7 items-center justify-center rounded text-ink-faint hover:bg-surface-hover"><Trash2 size={12} /></button>
            </div>
          ) : tasks.length === 0 ? (
            <p className="text-[12px] text-ink-faint">Нет задач. <button type="button" onClick={() => setAddingTask(true)} className="text-accent hover:underline">Создать</button></p>
          ) : (
            <div className="flex flex-col divide-y divide-border">
              {tasks.map((t) => (
                <div key={t.id} className="flex items-center gap-2 py-1.5">
                  <button type="button" disabled={taskBusyId === t.id} onClick={async () => { setTaskBusyId(t.id); try { await api.setTaskDone(t.id, !t.done); tasksState.reload(); } finally { setTaskBusyId(null); } }}
                    className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${t.done ? 'border-accent bg-accent text-white' : 'border-border-strong text-transparent hover:border-accent'} disabled:opacity-40`}>
                    {t.done && <Check size={9} />}
                  </button>
                  <Link to={`/?task=${t.id}`} className={`min-w-0 flex-1 truncate text-[12px] ${t.done ? 'text-ink-faint line-through' : 'text-ink'} hover:text-accent`}>{t.title}</Link>
                  {t.due_date && <span className="shrink-0 text-[11px] text-ink-faint">{formatTaskDeadline(t)}</span>}
                  <button type="button" disabled={taskBusyId === t.id} onClick={async () => { setTaskBusyId(t.id); try { await api.deleteTask(t.id); tasksState.reload(); } finally { setTaskBusyId(null); } }}
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-faint hover:bg-danger-subtle hover:text-danger"><Trash2 size={11} /></button>
                </div>
              ))}
              <button type="button" onClick={() => setAddingTask(true)} className="flex items-center gap-1 py-1 text-[11.5px] text-accent hover:underline"><Plus size={12} />Задача</button>
            </div>
          )}
        </div>
      )}

      {/* Utility row: mail ID + positions */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border px-4 sm:px-6 py-2 text-[12px] text-ink-muted">
        <span className="flex items-center gap-1">
          <Mail size={13} className="text-ink-faint" />
          <span className="font-medium text-ink-soft">Переписка</span>
          <span className="font-mono text-[11px] font-semibold text-accent">{request.email_reference}</span>
        </span>
        <button type="button" onClick={() => void copyEmailValue(externalEmailSubject, 'subject')}
          className="flex items-center gap-0.5 text-[11.5px] text-accent hover:text-accent-hover">
          {copiedEmailValue === 'subject' ? <Check size={12} /> : <Copy size={12} />} Тема
        </button>
        <button type="button" onClick={() => void copyEmailValue(request.email_reference, 'reference')}
          className="flex items-center gap-0.5 text-[11.5px] text-accent hover:text-accent-hover">
          {copiedEmailValue === 'reference' ? <Check size={12} /> : <Copy size={12} />} ID
        </button>
        <span className="hidden sm:inline truncate max-w-[200px] font-mono text-[11px] text-ink-faint" title={externalEmailSubject}>{externalEmailSubject}</span>
        {sentPreview && sentPreview.length > 0 ? (
          <button type="button" disabled={sentImporting} onClick={() => void importSentMail()}
            className="flex items-center gap-0.5 text-[11.5px] text-accent hover:text-accent-hover">
            <Check size={12} /> Импорт ({sentPreview.reduce((s, p) => s + p.count, 0)})
          </button>
        ) : (
          <button type="button" disabled={sentPreviewing || sentImporting} onClick={() => void previewSentMail()}
            className="flex items-center gap-0.5 text-[11.5px] text-ink-muted hover:text-accent">
            {sentPreviewing ? <Loader2 size={12} className="animate-spin" /> : <FolderSearch size={12} />} Найти в отправленных
          </button>
        )}
        <span aria-live="polite" className={sentSyncMessage ? 'text-[11px] text-ink-faint' : 'sr-only'}>{sentSyncMessage}</span>
      </div>

      {/* Positions */}
      {positions.length > 0 && (
        <div className="flex items-center gap-2 border-b border-border px-4 sm:px-6 py-1.5">
          <div className="flex items-center gap-1 text-[12px] font-medium text-ink">
            <Package size={13} className="text-ink-muted" />
            <span>Позиции</span>
            <span className="tabular-nums text-ink-faint font-normal">{positions.length}</span>
          </div>
          {positions.length <= 3 ? (
            <div className="flex flex-wrap gap-1.5">
              {positions.map((p) => (
                <span key={p.position_key} className="rounded bg-surface-hover px-2 py-0.5 text-[11.5px] text-ink-soft">
                  {p.name}{p.quantity ? <span className="text-ink-faint"> · {p.quantity}</span> : ''}
                </span>
              ))}
            </div>
          ) : (
            <>
              <button type="button" onClick={() => setPositionsExpanded((v) => !v)} className="flex items-center gap-0.5 text-[11.5px] text-ink-muted hover:text-ink">
                {positionsExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {positionsExpanded ? 'Скрыть' : `Показать все (${positions.length})`}
              </button>
              {!positionsExpanded && (
                <span className="text-[11.5px] text-ink-soft">{positions[0].name}{positions.length > 1 ? ` +${positions.length - 1}` : ''}</span>
              )}
              {positionsExpanded && (
                <div className="flex flex-wrap gap-1.5">
                  {positions.map((p) => (
                    <span key={p.position_key} className="rounded bg-surface-hover px-2 py-0.5 text-[11.5px] text-ink-soft">
                      {p.name}{p.quantity ? <span className="text-ink-faint"> · {p.quantity}</span> : ''}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Compact summary + filters */}
      <div className="border-b border-border px-4 sm:px-6 py-2">
        <div className="mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px]">
          <span className="font-medium text-ink">{suppliers.length}</span>
          <span className="text-ink-muted">поставщиков</span>
          <span className="h-3 w-px bg-border" />
          <span className="font-medium text-success">{counts.answered}</span>
          <span className="text-ink-muted">ответили</span>
          <span className="h-3 w-px bg-border" />
          <span className="font-medium text-warning">{counts.waiting}</span>
          <span className="text-ink-muted">ждут</span>
          <span className="h-3 w-px bg-border" />
          <span className="font-medium text-accent">{counts.attention}</span>
          <span className="text-ink-muted">требуют внимания</span>
          {metrics && (metrics.failed + metrics.bounced > 0 || metrics.delivery_unknown > 0) && (
            <>
              <span className="h-3 w-px bg-border" />
              <span className="font-medium text-danger">{metrics.failed + metrics.bounced + metrics.delivery_unknown}</span>
              <span className="text-ink-muted">проблем доставки</span>
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {FILTER_DEFS.filter(({ key }) => key === 'all' || counts[key] > 0).map(({ key, label }) => (
            <button key={key} type="button" onClick={() => setFilter(key)}
              className={`rounded px-2 py-0.5 text-[11.5px] font-medium transition-colors ${filter === key ? 'bg-accent text-white' : 'text-ink-muted hover:bg-surface-hover hover:text-ink'}`}>
              {label}<span className="ml-1 tabular-nums opacity-70">{counts[key]}</span>
            </button>
          ))}
          {selectedSuppliers.length > 0 && (
            <Button variant="primary" size="sm" icon={<Send size={12} />} onClick={() => setComposeOpen(true)}>
              Написать ({selectedSuppliers.length})
            </Button>
          )}
          <div className="relative ml-auto w-[200px]">
            <Search size={12} className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Поиск…"
              className="h-7 w-full rounded border border-border-strong bg-surface pl-6 pr-2 text-[12px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border" />
          </div>
        </div>
      </div>

      {/* Compose modal */}
      {(composeOpen || quickComposeSupplier) && (
        <BulkComposeModal
          requestId={requestId}
          recipients={composeRecipients.map(toSendInput)}
          onClose={() => { setComposeOpen(false); setQuickComposeId(null); }}
          onSent={() => { setSelected(new Set()); setQuickComposeId(null); reload(); }}
        />
      )}

      {/* Supplier table */}
      <div className="min-w-0 flex-1 overflow-auto">
        {suppliers.length === 0 ? (
          <EmptyState icon={Inbox} title="Поставщики ещё не найдены" />
        ) : visible.length === 0 ? (
          <EmptyState icon={Search} title="Ничего не найдено" />
        ) : (
          <>
            {/* Mobile cards */}
            <div className="flex flex-col divide-y divide-border sm:hidden">
              {visible.map((s) => {
                const ctx = statusContext(s);
                return (
                  <div key={s.id} className={`flex flex-col gap-2 px-4 py-3 ${selected.has(s.id) ? 'bg-accent-subtle/30' : ''}`}>
                    <div className="flex items-start gap-2">
                      <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggleSelected(s.id)} disabled={!s.email}
                        aria-label={`Выбрать ${s.name}`} className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded border-border-strong accent-accent disabled:opacity-30" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          {s.global_supplier_id ? (
                            <Link to={`/suppliers/${s.global_supplier_id}`} className="truncate font-medium text-ink hover:text-accent">{formatCompanyName(s.name)}</Link>
                          ) : (
                            <p className="truncate font-medium text-ink">{formatCompanyName(s.name)}</p>
                          )}
                          <Badge tone={ctx.tone}>{ctx.label}</Badge>
                        </div>
                        <p className="truncate text-[11px] text-ink-muted">{s.email || 'Нет email'}{s.inn ? ` · ИНН ${s.inn}` : ''}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-1.5">
                      {s.email && (
                        <button type="button" onClick={() => setQuickComposeId(s.id)} title="Написать" aria-label="Написать"
                          className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-subtle text-accent hover:bg-accent hover:text-white"><Send size={13} /></button>
                      )}
                      <button type="button" onClick={() => openThread(s.id)} title="Переписка" aria-label="Переписка"
                        className="flex h-7 w-7 items-center justify-center rounded-full bg-info-subtle text-info hover:bg-info hover:text-white"><MessageSquareText size={13} /></button>
                      <button type="button" disabled={irrelevantId === s.id} onClick={() => void markIrrelevant(s.id)} title="Не подходит"
                        className="flex h-7 w-7 items-center justify-center rounded-full bg-danger-subtle text-danger hover:bg-danger hover:text-white disabled:opacity-50"><Ban size={13} /></button>
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Desktop table */}
            <div className="hidden sm:block overflow-x-auto">
              <table className="w-full min-w-[900px] table-fixed border-collapse text-[12.5px]">
                <colgroup>
                  <col className="w-9" />
                  <col className="w-[22%]" />
                  <col className="w-[18%]" />
                  <col className="w-[13%]" />
                  <col className="w-[12%]" />
                  <col className="w-[9%]" />
                  <col className="w-[9%]" />
                  <col className="w-[80px]" />
                </colgroup>
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-3 py-1.5 pl-6">
                      <input type="checkbox" checked={visible.length > 0 && visible.every((s) => selected.has(s.id))}
                        onChange={toggleSelectAll} aria-label="Выбрать всех" className="h-3.5 w-3.5 rounded border-border-strong accent-accent" />
                    </th>
                    <th className="px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">Компания</th>
                    <th className="px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">Контакты</th>
                    <th className="px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">Коммуникация</th>
                    <th className="px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-ink-muted">Действие</th>
                    <th className="px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">Метрики</th>
                    <th className="px-3 py-1.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">ЕГРЮЛ</th>
                    <th className="px-3 py-1.5 pr-6" />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((s) => {
                    const ctx = statusContext(s);
                    const action = primaryActionFor(s);
                    const age = companyAge(s.registry?.registered_at);
                    const checko = checkoUrl(s.registry?.ogrn);
                    const site = s.host ? (s.host.startsWith('http') ? s.host : `https://${s.host}`) : null;
                    return (
                      <tr key={s.id} className={`border-b border-border last:border-0 hover:bg-surface-hover ${selected.has(s.id) ? 'bg-accent-subtle/30' : ''}`}>
                        <td className="px-3 py-2 pl-6 align-top">
                          <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggleSelected(s.id)} disabled={!s.email}
                            title={s.email ? undefined : 'Нет email'} className="h-3.5 w-3.5 rounded border-border-strong accent-accent disabled:opacity-30" />
                        </td>
                        <td className="px-3 py-2 align-top">
                          <div className="min-w-0">
                            {s.global_supplier_id ? (
                              <Link to={`/suppliers/${s.global_supplier_id}`} onClick={(e) => e.stopPropagation()}
                                className="truncate font-medium text-ink hover:text-accent hover:underline">{formatCompanyName(s.name)}</Link>
                            ) : (
                              <p className="truncate font-medium text-ink" title="Карточка появится после ИНН">{formatCompanyName(s.name)}</p>
                            )}
                            <p className="truncate text-[11px] text-ink-faint">
                              {s.inn && <span>ИНН {s.inn}</span>}{s.inn && s.region ? <span className="text-ink-faint"> · {s.region}</span> : ''}
                            </p>
                            {site && (
                              <a href={site} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-0.5 text-[11px] text-accent hover:underline">
                                {s.host} <ExternalLink size={8} />
                              </a>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2 align-top">
                          {s.email ? (
                            <span className="flex items-center gap-1"><span className="truncate text-ink-soft">{s.email}</span><CopyButton text={s.email} /></span>
                          ) : (
                            <span className="text-ink-faint">Нет email</span>
                          )}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <div className="flex items-center gap-1.5">
                            <Badge tone={ctx.tone}>{ctx.label}</Badge>
                            {s.unread_count > 0 && (
                              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white">{s.unread_count}</span>
                            )}
                          </div>
                        </td>
                        <td className="px-3 py-2 align-top">
                          {action === 'compose' && (
                            <button type="button" onClick={() => setQuickComposeId(s.id)}
                              className="inline-flex h-6 items-center gap-1 rounded-md bg-accent-subtle px-2 text-[11px] font-medium text-accent hover:bg-accent hover:text-white">
                              <Send size={11} /> Написать
                            </button>
                          )}
                          {action === 'thread' && (
                            <button type="button" onClick={() => openThread(s.id)}
                              className="inline-flex h-6 items-center gap-1 rounded-md bg-info-subtle px-2 text-[11px] font-medium text-info hover:bg-info hover:text-white">
                              <MessageSquareText size={11} /> Переписка
                            </button>
                          )}
                          {action === 'add_contact' && <span className="text-[11px] text-ink-faint">Нет email</span>}
                        </td>
                        <td className="px-3 py-2 align-top text-[11px] text-ink-faint">
                          {age && <span className="block">{age}</span>}
                          {s.finances?.revenue != null && <span className="block">{formatMoney(s.finances.revenue)}</span>}
                        </td>
                        <td className="px-3 py-2 align-top">
                          {s.registry ? (
                            <span className={`text-[11px] ${s.registry.is_active === false ? 'text-danger' : 'text-success'}`}>
                              {s.registry.is_active === false ? 'Ликвидировано' : s.registry.status || 'Действует'}
                            </span>
                          ) : <span className="text-[11px] text-ink-faint">—</span>}
                        </td>
                        <td className="px-3 py-2 pr-6 align-top">
                          <div className="flex items-center justify-end gap-1">
                            {checko && (
                              <a href={checko} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} title="Checko"
                                className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover">
                                <img src={checkoIcon} alt="Checko" className="h-3.5 w-3.5" />
                              </a>
                            )}
                            <button type="button" onClick={(e) => { e.stopPropagation(); setQuickComposeId(s.id); }} title="Написать"
                              className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover hover:text-ink"><Send size={11} /></button>
                            <button type="button" onClick={(e) => { e.stopPropagation(); openThread(s.id); }} title="Переписка"
                              className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-surface-hover hover:text-ink"><MessageSquareText size={11} /></button>
                            <button type="button" disabled={irrelevantId === s.id} onClick={() => void markIrrelevant(s.id)} title="Не подходит"
                              className="flex h-6 w-6 items-center justify-center rounded text-ink-faint hover:bg-danger-subtle hover:text-danger disabled:opacity-50"><Ban size={11} /></button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}