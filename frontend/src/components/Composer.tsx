import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CheckCircle2,
  ChevronLeft,
  Eye,
  FileWarning,
  Loader2,
  Paperclip,
  Send,
  ShieldAlert,
  X,
} from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import { RichTextEditor } from './mail/RichTextEditor';
import { plainTextToHtml } from './mail/richTextUtils';
import type { MailAccount, PreflightRecipientResult, PreflightResult, PreviewTarget, Supplier } from '@/lib/types';

interface Props {
  open: boolean;
  requestId: number;
  suppliers: Supplier[];
  selectedIds: Set<number>;
  onClose: () => void;
  onCampaignCreated: (campaignId: number) => void;
}

export interface PendingAttachment {
  filename: string;
  mime_type: string;
  content_base64: string;
  size: number;
}

const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024;
const ALLOWED_MIME_PREFIXES = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument', 'text/plain', 'image/'];
const DEFAULT_SUBJECT = 'Запрос коммерческого предложения';
const DEFAULT_BODY = 'Добрый день!\n\nПросим предоставить коммерческое предложение.';

const REASON_LABELS: Record<string, string> = {
  duplicate: 'Дубликат адреса',
  duplicate_recipient: 'Дубликат адреса',
  invalid_email: 'Некорректный email',
  suppressed: 'Адрес в списке «не писать»',
  hard_bounce: 'Постоянный отказ доставки',
  unresolved_safety_state: 'Предыдущая отправка требует проверки',
  already_contacted: 'Уже обращались в этой заявке',
  answered: 'Получен ответ по этой заявке',
  queued: 'Письмо уже ожидает отправки',
  accepted: 'Письмо уже отправлено',
  failed: 'Предыдущая отправка завершилась ошибкой',
  bounced: 'Письмо не доставлено',
  delivery_unknown: 'Результат предыдущей отправки неизвестен',
  cancelled: 'Предыдущая отправка отменена',
  no_eligible_email: 'Нет доступного неиспользованного email',
  ambiguous_supplier_identity: 'Нельзя однозначно определить компанию',
  same_request_already_contacted: 'Для этой заявки email уже был использован',
  no_eligible_recipients: 'Нет получателей для новой отправки',
  missing_email: 'Email отсутствует',
  attachment_limit: 'Превышен размер вложений',
  attachment_over_limit_or_invalid: 'Вложение не проходит ограничения',
  render_error: 'Не удалось собрать письмо',
};

const WARNING_LABELS: Record<string, string> = {
  provider_policy_warning: 'Провайдер может ограничить массовую однотипную рассылку.',
  high_content_similarity: 'Большая часть писем практически одинакова.',
  missing_supplier_context: 'Для части поставщиков мало данных для персонализации.',
  many_recipients_same_domain: 'В партии много адресов одного домена.',
  large_campaign_review: 'Большая партия требует внимательной проверки.',
  subject_same_for_large_batch: 'Тема одинакова у большой части партии.',
  campaign_exceeds_daily_budget: 'Размер кампании больше текущего rolling 24-часового бюджета аккаунта.',
  some_recipients_skipped: 'Часть компаний пропущена: в этой заявке им уже писали.',
  shared_email_across_companies: 'Один email связан с несколькими компаниями. Компании не объединяются автоматически.',
  explicit_repeat_enabled: 'Включён явный повтор для уже использованных email.',
};

function isAllowedMime(mime: string): boolean {
  return ALLOWED_MIME_PREFIXES.some((prefix) => mime === prefix || mime.startsWith(prefix));
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} КБ` : `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function formatDurationValue(seconds: number): string {
  const numericSeconds = Number(seconds);
  if (!Number.isFinite(numericSeconds) || numericSeconds < 60) return 'меньше минуты';
  const minutes = Math.max(1, Math.round(numericSeconds / 60));
  if (minutes < 60) return `${minutes} мин.`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} ч ${rest} мин.` : `${hours} ч`;
}

function formatDuration(seconds: number): string {
  return `около ${formatDurationValue(seconds)}`;
}

function formatInterval(seconds: number): string {
  const numeric = Number(seconds);
  if (!Number.isFinite(numeric)) return '—';
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
}

function pacingRange(result: PreflightResult): string {
  return `${formatInterval(result.pacing.min_interval_seconds)}–${formatInterval(result.pacing.max_interval_seconds)} с`;
}

function createIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return `mail-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? reason.replace(/_/g, ' ');
}

function warningLabel(warning: string): string {
  return WARNING_LABELS[warning] ?? warning.replace(/_/g, ' ');
}

function blockLabel(block: string, result: PreflightResult): string {
  if (block === 'campaign_size_out_of_range') {
    if (result.planned <= 0) return 'Выберите хотя бы одного получателя.';
    const removeCount = Math.max(0, result.planned - result.campaign_limits.max_recipients);
    const word = removeCount === 1 || (removeCount >= 2 && removeCount <= 4) ? 'получателя' : 'получателей';
    return `Выбрано ${result.planned}. Максимум для одной кампании — ${result.campaign_limits.max_recipients}. Уберите ещё ${removeCount} ${word}.`;
  }
  return reasonLabel(block);
}

function rolloutPlan(result: PreflightResult): string {
  return `${result.rollout.stage_1} → ${result.rollout.stage_2} → ${result.rollout.stage_3} → все (${result.eligible})`;
}

function statusLabel(status: PreflightResult['status']): string {
  return status === 'PASS' ? 'Можно запускать' : status === 'WARNING' ? 'Нужна проверка' : 'Запуск заблокирован';
}

function personalizeLabel(level: number): string {
  if (level >= 3) return 'Расширенная';
  if (level === 2) return 'Компания и запрос';
  if (level === 1) return 'По компании';
  return 'Без персонализации';
}

function sameRecipients(a: PreflightResult | null, b: PreflightResult | null): boolean {
  if (!a || !b) return false;
  const stablePreviews = (result: PreflightResult) => (result.previews ?? []).map((item) => ({
    to_email: item.to_email,
    subject: item.subject,
    body_text: item.body_text,
    body_html: item.body_html,
    personalization_level: item.personalization_level,
  }));
  return JSON.stringify({ status: a.status, eligible: a.eligible, excluded: a.excluded, recipient_results: a.recipient_results, previews: stablePreviews(a) }) === JSON.stringify({ status: b.status, eligible: b.eligible, excluded: b.excluded, recipient_results: b.recipient_results, previews: stablePreviews(b) });
}

export function Composer({ open, requestId, suppliers, selectedIds, onClose, onCampaignCreated }: Props) {
  const [subject, setSubject] = useState(DEFAULT_SUBJECT);
  const [body, setBody] = useState(DEFAULT_BODY);
  const [bodyHtml, setBodyHtml] = useState(() => plainTextToHtml(DEFAULT_BODY));
  const [editorInitialHtml, setEditorInitialHtml] = useState(() => plainTextToHtml(DEFAULT_BODY));
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [manualEmails, setManualEmails] = useState<string[]>([]);
  const [manualInput, setManualInput] = useState('');
  const [manualError, setManualError] = useState('');
  const [excludedIds, setExcludedIds] = useState<Set<number>>(new Set());
  const [senderEmail, setSenderEmail] = useState<string | null>(null);
  const [mailAccounts, setMailAccounts] = useState<MailAccount[]>([]);
  const [mailAccountId, setMailAccountId] = useState<number | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateWarning, setTemplateWarning] = useState('');
  const [attachError, setAttachError] = useState('');
  const [error, setError] = useState('');
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preview, setPreview] = useState<PreflightResult | null>(null);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [phase, setPhase] = useState<'edit' | 'review' | 'confirm'>('edit');
  const [checking, setChecking] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState(false);
  const [manualStageApproval, setManualStageApproval] = useState<boolean | null>(null);
  const [allowRepeat, setAllowRepeat] = useState(false);
  const intentKeyRef = useRef<{ signature: string; key: string } | null>(null);
  const checkedSignatureRef = useRef<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstControlRef = useRef<HTMLButtonElement>(null);

  const allSelectedRecipients = useMemo(() => suppliers.filter((supplier) => selectedIds.has(supplier.id) && supplier.email), [suppliers, selectedIds]);
  const selectedRecipients = useMemo(() => allSelectedRecipients.filter((supplier) => !excludedIds.has(supplier.id)), [allSelectedRecipients, excludedIds]);
  const payloadSuppliers = useMemo(() => [
    ...selectedRecipients.map((supplier) => ({
      id: supplier.id,
      email: supplier.email as string,
      name: supplier.name,
      host: supplier.host,
      external_key: supplier.external_key,
      inn: supplier.inn,
      global_supplier_id: supplier.global_supplier_id,
    })),
    ...manualEmails.map((email) => ({ email, name: email })),
  ], [selectedRecipients, manualEmails]);
  const draftSignature = useMemo(() => JSON.stringify({ requestId, mail_account_id: mailAccountId, suppliers: payloadSuppliers, subject, body, body_html: bodyHtml, allow_repeat: allowRepeat, attachments: attachments.map(({ filename, mime_type, content_base64 }) => ({ filename, mime_type, content_base64 })) }), [requestId, mailAccountId, payloadSuppliers, subject, body, bodyHtml, allowRepeat, attachments]);
  const intentSignature = useMemo(() => JSON.stringify({ draftSignature, manual_stage_approval: manualStageApproval, allow_repeat: allowRepeat }), [draftSignature, manualStageApproval, allowRepeat]);
  const currentPreview = preview?.previews?.[Math.min(previewIndex, Math.max(0, (preview?.previews?.length ?? 1) - 1))] ?? null;
  const supplierByEmail = useMemo(() => {
    const map = new Map<string, Supplier>();
    suppliers.forEach((supplier) => {
      if (supplier.email) map.set(supplier.email.toLowerCase(), supplier);
      (supplier.contacts ?? []).forEach((contact) => map.set(contact.email.toLowerCase(), supplier));
    });
    return map;
  }, [suppliers]);
  const excludedRows = (preflight?.recipient_results ?? []).filter((recipient) => recipient.status === 'excluded');
  const totalRecipients = payloadSuppliers.length;
  const availableAccounts = useMemo(() => mailAccounts.filter((account) => account.connected && account.outgoing_enabled), [mailAccounts]);

  useEffect(() => {
    if (!open) return undefined;
    let cancelled = false;
    setSubject(DEFAULT_SUBJECT); setBody(DEFAULT_BODY); setBodyHtml(plainTextToHtml(DEFAULT_BODY)); setEditorInitialHtml(plainTextToHtml(DEFAULT_BODY)); setAttachments([]); setManualEmails([]); setManualInput(''); setManualError(''); setExcludedIds(new Set()); setSenderEmail(null); setTemplateWarning(''); setAttachError(''); setError(''); setPreflight(null); setPreview(null); setPreviewIndex(0); setPhase('edit'); setAcknowledgedWarnings(false); setManualStageApproval(null); setAllowRepeat(false); intentKeyRef.current = null; checkedSignatureRef.current = null;
    setTemplateLoading(true);
    void api.mailStatus().then((status) => {
      if (cancelled) return;
      const connected = (status.accounts ?? []).filter((account) => account.connected && account.outgoing_enabled);
      setMailAccounts(status.accounts ?? []);
      const preferred = connected.find((account) => account.provider === 'yandex') ?? connected[0] ?? null;
      setMailAccountId(preferred?.id ?? null);
      setSenderEmail(preferred?.email ?? (status.connected ? status.email ?? null : null));
    }).catch(() => { if (!cancelled) { setMailAccounts([]); setMailAccountId(null); setSenderEmail(null); } });
    void api.mailTemplate().then((template) => { if (!cancelled) { const templateHtml = plainTextToHtml(template.body); setSubject(template.subject); setBody(template.body); setBodyHtml(templateHtml); setEditorInitialHtml(templateHtml); setAttachments(template.attachments); } }).catch(() => { if (!cancelled) setTemplateWarning('Шаблон не загрузился. Проверьте текст перед запуском.'); }).finally(() => { if (!cancelled) setTemplateLoading(false); });
    return () => { cancelled = true; };
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const previous = document.activeElement as HTMLElement | null;
    firstControlRef.current?.focus();
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' && !checking && !previewLoading && !starting) { onClose(); return; }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [contenteditable="true"], [href]'));
      if (!focusable.length) return;
      const first = focusable[0]; const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => { window.removeEventListener('keydown', handleKeyDown); previous?.focus(); };
  }, [open, checking, previewLoading, starting, onClose]);

  useEffect(() => {
    if (!checkedSignatureRef.current || checkedSignatureRef.current === draftSignature) return;
    setPreflight(null); setPreview(null); setPhase('edit'); setAcknowledgedWarnings(false); setError('');
  }, [draftSignature]);

  if (!open) return null;

  const addManualEmail = () => {
    const value = manualInput.trim().toLowerCase();
    if (!value) return;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value)) { setManualError('Похоже, это не адрес электронной почты.'); return; }
    if (manualEmails.includes(value) || allSelectedRecipients.some((supplier) => supplier.email?.toLowerCase() === value)) { setManualError('Этот адрес уже в списке получателей.'); return; }
    setManualEmails((current) => [...current, value]); setManualInput(''); setManualError('');
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setAttachError('');
    let total = attachments.reduce((sum, attachment) => sum + attachment.size, 0);
    const next: PendingAttachment[] = [];
    for (const file of Array.from(files)) {
      const mime = file.type || 'application/octet-stream';
      if (!isAllowedMime(mime)) { setAttachError(`«${file.name}»: разрешены PDF, DOC/DOCX, TXT и изображения.`); continue; }
      if (file.size > MAX_ATTACHMENT_BYTES) { setAttachError(`«${file.name}»: файл больше 10 МБ.`); continue; }
      if (total + file.size > MAX_TOTAL_ATTACHMENT_BYTES) { setAttachError('Суммарный размер вложений не должен превышать 20 МБ.'); break; }
      total += file.size; next.push({ filename: file.name, mime_type: mime, content_base64: await readFileAsBase64(file), size: file.size });
    }
    if (next.length) setAttachments((current) => [...current, ...next]);
  };

  const runPreflight = async () => {
    if (!payloadSuppliers.length) { setError('Добавьте хотя бы одного получателя.'); return; }
    setChecking(true); setError('');
    try {
      const result = await api.preflightBulk({ request_id: requestId, mail_account_id: mailAccountId ?? undefined, suppliers: payloadSuppliers, subject, body_text: body, body_html: bodyHtml, attachments, manual_stage_approval: manualStageApproval ?? undefined, allow_repeat: allowRepeat });
      checkedSignatureRef.current = draftSignature; setManualStageApproval(result.rollout.manual_stage_approval); setPreflight(result); setPreview(null); setPreviewIndex(0); setAcknowledgedWarnings(false); setPhase('review');
    } catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Не удалось проверить рассылку.'); } finally { setChecking(false); }
  };

  const loadPreview = async () => {
    setPreviewLoading(true); setError('');
      try { const result = await api.previewBulk({ request_id: requestId, mail_account_id: mailAccountId ?? undefined, suppliers: payloadSuppliers, subject, body_text: body, body_html: bodyHtml, attachments, manual_stage_approval: manualStageApproval ?? undefined, allow_repeat: allowRepeat }); setPreview(result); setPreviewIndex(0); }
    catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Не удалось собрать предпросмотр.'); }
    finally { setPreviewLoading(false); }
  };

  const startCampaign = async () => {
    if (!preflight || preflight.status === 'BLOCK' || (preflight.status === 'WARNING' && !acknowledgedWarnings)) return;
    setStarting(true); setError('');
    try {
      const selectedManualStageApproval = manualStageApproval ?? preflight.rollout.manual_stage_approval;
      // There is no backend freshness token. Re-run preflight immediately before
      // send-bulk. The idempotency key is retained if this POST must be retried.
      const finalPreflight = await api.preflightBulk({ request_id: requestId, mail_account_id: mailAccountId ?? undefined, suppliers: payloadSuppliers, subject, body_text: body, body_html: bodyHtml, attachments, manual_stage_approval: selectedManualStageApproval, allow_repeat: allowRepeat });
      if (finalPreflight.status === 'BLOCK') { checkedSignatureRef.current = draftSignature; setPreflight(finalPreflight); setPreview(null); setPhase('review'); setAcknowledgedWarnings(false); setError('Проверка перед запуском нашла новую блокирующую причину. Ничего не отправлено.'); return; }
      if (!sameRecipients(preflight, finalPreflight)) { checkedSignatureRef.current = draftSignature; setPreflight(finalPreflight); setPreview(null); setPhase('review'); setAcknowledgedWarnings(false); setError('Данные кампании изменились. Проверьте обновлённый результат перед запуском.'); return; }
      const currentIntent = intentKeyRef.current;
      const idempotencyKey = currentIntent?.signature === intentSignature ? currentIntent.key : createIdempotencyKey();
      intentKeyRef.current = { signature: intentSignature, key: idempotencyKey };
      const response = await api.sendMailBulk({ request_id: requestId, mail_account_id: mailAccountId ?? undefined, suppliers: payloadSuppliers, subject, body_text: body, body_html: bodyHtml, attachments, idempotency_key: idempotencyKey, manual_stage_approval: selectedManualStageApproval, allow_repeat: allowRepeat });
      const campaignId = response.queued.find((item) => item.campaign_id != null)?.campaign_id;
      if (campaignId == null) throw new Error('Сервер не вернул идентификатор кампании.');
      onCampaignCreated(campaignId);
    } catch (requestError) { setError(requestError instanceof ApiError ? requestError.message : 'Не удалось запустить кампанию. Ключ операции сохранён — повтор не создаст новую кампанию.'); }
    finally { setStarting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/35 p-3 sm:p-5" onMouseDown={(event) => { if (event.target === event.currentTarget && !starting) onClose(); }}>
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="campaign-composer-title" className="flex max-h-[94vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-panel">
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-ink-100 px-4 py-4 sm:px-6">
          <div className="min-w-0"><div className="mb-1 flex items-center gap-2 text-2xs font-bold uppercase tracking-[0.16em] text-accent-600"><span className="h-1.5 w-1.5 rounded-full bg-accent-600" />Кампания</div><h2 id="campaign-composer-title" className="text-lg font-bold tracking-tight text-ink-900">Подготовка рассылки</h2><div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs font-medium text-ink-400" aria-label="Этапы подготовки"><span className={phase === 'edit' ? 'text-accent-700' : 'text-ink-500'}>1. Письмо</span><span>→</span><span className={phase === 'review' ? 'text-accent-700' : 'text-ink-500'}>2. Проверка</span><span>→</span><span className={phase === 'confirm' ? 'text-accent-700' : 'text-ink-500'}>3. Запуск</span></div></div>
          <button type="button" onClick={onClose} aria-label="Закрыть подготовку рассылки" disabled={starting} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-400 transition hover:bg-ink-100 hover:text-ink-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 disabled:opacity-50"><X className="h-5 w-5" /></button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
          {phase === 'edit' && <RepeatControl allowRepeat={allowRepeat} onChange={(value) => { setAllowRepeat(value); setPreflight(null); setPreview(null); setPhase('edit'); setError(''); }} />}
          {phase === 'edit' && <div className="space-y-5">
            <div className="flex flex-wrap items-end justify-between gap-3 rounded-xl border border-ink-200 bg-ink-50/60 px-4 py-3"><div className="min-w-0 flex-1"><label htmlFor="campaign-mail-account" className="text-xs font-semibold text-ink-500">Почтовый аккаунт</label>{availableAccounts.length ? <select id="campaign-mail-account" value={mailAccountId ?? ''} onChange={(event) => { setMailAccountId(Number(event.target.value) || null); setPreflight(null); setPreview(null); setPhase('edit'); }} className="mt-1 h-10 w-full max-w-md rounded-lg border border-ink-200 bg-white px-3 text-sm font-semibold text-ink-900 focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-100">{availableAccounts.map((account) => <option key={account.id} value={account.id}>{account.provider === 'mailru' ? 'Mail.ru' : 'Яндекс.Почта'} · {account.email}</option>)}</select> : <p className="mt-0.5 truncate text-sm font-semibold text-ink-900">{senderEmail ?? 'Почта не подключена'}</p>}<p className="mt-1 text-2xs text-ink-500">Можно выбрать аккаунт перед проверкой и запуском.</p></div><div className="text-left sm:text-right"><p className="text-xs font-semibold text-ink-500">Получатели</p><p className="mt-0.5 text-sm font-bold tabular-nums text-ink-900">{totalRecipients}</p></div></div>
            <section aria-labelledby="campaign-recipients-title" className="rounded-xl border border-ink-200"><div className="flex items-center justify-between gap-3 border-b border-ink-100 px-4 py-3"><div><h3 id="campaign-recipients-title" className="text-sm font-bold text-ink-900">Кому отправим</h3><p className="mt-0.5 text-xs text-ink-500">Проверьте список до запуска проверки.</p></div><span className="rounded-full bg-accent-50 px-2.5 py-1 text-xs font-bold text-accent-700">{totalRecipients}</span></div><div className="max-h-48 divide-y divide-ink-100 overflow-y-auto">{allSelectedRecipients.map((supplier) => { const excluded = excludedIds.has(supplier.id); return <label key={supplier.id} className={`flex min-w-0 cursor-pointer items-center gap-3 px-4 py-3 ${excluded ? 'bg-ink-50 opacity-55' : ''}`}><input type="checkbox" checked={!excluded} onChange={() => setExcludedIds((current) => { const next = new Set(current); if (next.has(supplier.id)) next.delete(supplier.id); else next.add(supplier.id); return next; })} className="h-4 w-4 shrink-0 accent-accent-600" /><span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold text-ink-800" title={supplier.name}>{supplier.name}</span><span className="block truncate text-xs text-ink-500" title={supplier.email ?? undefined}>{supplier.email}</span></span>{supplier.global_supplier_id != null && <a href={`/suppliers?open=${supplier.global_supplier_id}`} target="_blank" rel="noreferrer" aria-label={`Открыть карточку ${supplier.name}`} className="shrink-0 text-ink-400 hover:text-accent-600"><Building2 className="h-4 w-4" /></a>}</label>; })}{manualEmails.map((email) => <div key={email} className="flex min-w-0 items-center gap-3 px-4 py-3"><span className="shrink-0 rounded-full bg-accent-50 px-2 py-0.5 text-2xs font-bold text-accent-700">вручную</span><span className="min-w-0 flex-1 truncate text-sm text-ink-700" title={email}>{email}</span><button type="button" onClick={() => setManualEmails((current) => current.filter((item) => item !== email))} aria-label={`Убрать ${email}`} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-400 hover:bg-rose-50 hover:text-rose-600"><X className="h-4 w-4" /></button></div>)}{!allSelectedRecipients.length && !manualEmails.length && <p className="px-4 py-5 text-sm text-ink-500">Нет получателей с email. Добавьте адрес ниже.</p>}</div><div className="border-t border-ink-100 px-4 py-3"><div className="flex flex-col gap-2 sm:flex-row"><input type="email" value={manualInput} onChange={(event) => { setManualInput(event.target.value); setManualError(''); }} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addManualEmail(); } }} aria-label="Добавить получателя вручную" placeholder="Добавить адрес вручную…" className="h-10 min-w-0 flex-1 rounded-lg border border-ink-200 px-3 text-sm text-ink-800 outline-none transition focus:border-accent-400 focus:ring-2 focus:ring-accent-100" /><button type="button" onClick={addManualEmail} disabled={!manualInput.trim()} className="min-h-10 rounded-lg border border-ink-200 px-4 text-sm font-semibold text-ink-700 hover:border-accent-300 hover:text-accent-700 disabled:cursor-not-allowed disabled:opacity-50">Добавить адрес</button></div>{manualError && <p role="alert" className="mt-2 text-xs font-medium text-rose-600">{manualError}</p>}</div></section>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]"><div className="space-y-4"><div><label htmlFor="campaign-subject" className="mb-1.5 block text-xs font-bold text-ink-700">Тема письма</label><input id="campaign-subject" value={subject} onChange={(event) => setSubject(event.target.value)} disabled={templateLoading} className="h-11 w-full rounded-lg border border-ink-200 px-3 text-sm text-ink-800 outline-none transition focus:border-accent-400 focus:ring-2 focus:ring-accent-100 disabled:bg-ink-50" /></div><div><label htmlFor="campaign-body" className="mb-1.5 block text-xs font-bold text-ink-700">Текст письма</label><RichTextEditor id="campaign-body" initialHtml={editorInitialHtml} ariaLabel="Текст письма кампании" placeholder="Напишите письмо…" disabled={templateLoading} onChange={({ bodyText: nextBodyText, bodyHtml: nextBodyHtml }) => { setBody(nextBodyText); setBodyHtml(nextBodyHtml); }} /></div>{templateLoading && <p role="status" className="flex items-center gap-2 text-xs text-ink-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Загружаем сохранённый шаблон…</p>}{templateWarning && <p role="status" className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-800"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />{templateWarning}</p>}</div><aside className="rounded-xl border border-ink-200 bg-ink-50/50 p-4"><div className="flex items-center gap-2 text-sm font-bold text-ink-800"><Paperclip className="h-4 w-4 text-ink-400" />Вложения</div><p className="mt-1 text-xs leading-5 text-ink-500">До 10 МБ на файл и 20 МБ суммарно.</p><label className="mt-4 inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg border border-ink-200 bg-white px-3 text-xs font-bold text-ink-700 hover:border-accent-300 hover:text-accent-700">Выбрать файлы<input type="file" multiple aria-label="Прикрепить файлы к кампании" className="sr-only" onChange={(event) => { void handleFiles(event.target.files); event.target.value = ''; }} /></label>{attachError && <p role="alert" className="mt-2 text-xs text-rose-600">{attachError}</p>}{attachments.length > 0 && <ul className="mt-3 space-y-2">{attachments.map((attachment) => <li key={attachment.filename} className="flex min-w-0 items-center gap-2 text-xs"><Paperclip className="h-3.5 w-3.5 shrink-0 text-ink-400" /><span className="min-w-0 flex-1 truncate" title={attachment.filename}>{attachment.filename}</span><span className="shrink-0 text-ink-400">{formatSize(attachment.size)}</span><button type="button" onClick={() => setAttachments((current) => current.filter((item) => item.filename !== attachment.filename))} aria-label={`Убрать вложение ${attachment.filename}`} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-ink-400 hover:bg-rose-50 hover:text-rose-600"><X className="h-3.5 w-3.5" /></button></li>)}</ul>}</aside></div>
            {error && <p role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>}
          </div>}

          {phase === 'review' && preflight && <PreflightReview result={preflight} manualStageApproval={manualStageApproval ?? preflight.rollout.manual_stage_approval} onManualStageApprovalChange={setManualStageApproval} excludedRows={excludedRows} supplierByEmail={supplierByEmail} preview={preview} previewIndex={previewIndex} currentPreview={currentPreview} previewLoading={previewLoading} acknowledgedWarnings={acknowledgedWarnings} onAcknowledgeWarnings={setAcknowledgedWarnings} onLoadPreview={() => void loadPreview()} onSelectPreview={setPreviewIndex} onBack={() => { setPhase('edit'); setError(''); }} onContinue={() => { setPhase('confirm'); setError(''); }} error={error} />}
          {phase === 'confirm' && preflight && <ConfirmationView result={preflight} manualStageApproval={manualStageApproval ?? preflight.rollout.manual_stage_approval} onBack={() => setPhase('review')} onStart={() => void startCampaign()} starting={starting} error={error} />}
        </div>

        <div className="flex shrink-0 flex-col-reverse gap-2 border-t border-ink-100 bg-ink-50/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">{phase === 'edit' ? <><button type="button" onClick={onClose} disabled={checking} className="min-h-10 rounded-lg px-3 text-sm font-semibold text-ink-600 hover:bg-white disabled:opacity-50">Отмена</button><button ref={firstControlRef} type="button" onClick={() => void runPreflight()} disabled={checking || templateLoading || !totalRecipients} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-bold text-white shadow-soft transition hover:bg-accent-700 disabled:cursor-wait disabled:opacity-50">{checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldAlert className="h-4 w-4" />}{checking ? 'Проверяем…' : 'Проверить рассылку'}</button></> : <div className="flex w-full items-center justify-between gap-2"><button type="button" onClick={() => { setPhase('edit'); setError(''); }} disabled={starting || previewLoading} className="inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-ink-600 hover:bg-white disabled:opacity-50"><ChevronLeft className="h-4 w-4" />Назад к письму</button><span className="hidden text-xs text-ink-400 sm:block">Проверка и предпросмотр не отправляют письма</span></div>}</div>
      </div>
    </div>
  );
}

function PreflightReview({ result, manualStageApproval, onManualStageApprovalChange, excludedRows, supplierByEmail, preview, previewIndex, currentPreview, previewLoading, acknowledgedWarnings, onAcknowledgeWarnings, onLoadPreview, onSelectPreview, onBack, onContinue, error }: { result: PreflightResult; manualStageApproval: boolean; onManualStageApprovalChange: (value: boolean) => void; excludedRows: PreflightRecipientResult[]; supplierByEmail: Map<string, Supplier>; preview: PreflightResult | null; previewIndex: number; currentPreview: PreviewTarget | null; previewLoading: boolean; acknowledgedWarnings: boolean; onAcknowledgeWarnings: (value: boolean) => void; onLoadPreview: () => void; onSelectPreview: (index: number) => void; onBack: () => void; onContinue: () => void; error: string }) {
  const blocked = result.status === 'BLOCK';
  return <div className="space-y-5">
    <SelectionSummary result={result} />
    <div className="flex flex-col gap-3 rounded-2xl border border-ink-200 bg-white p-4 shadow-soft sm:flex-row sm:items-center sm:justify-between sm:p-5"><div className="flex min-w-0 items-start gap-3"><div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${blocked ? 'bg-rose-50 text-rose-600' : result.status === 'WARNING' ? 'bg-amber-50 text-amber-600' : 'bg-emerald-50 text-emerald-600'}`}>{blocked ? <ShieldAlert className="h-5 w-5" /> : result.status === 'WARNING' ? <AlertTriangle className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}</div><div className="min-w-0"><p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-400">Результат проверки</p><h3 className="mt-1 text-lg font-bold text-ink-900">{statusLabel(result.status)}</h3><p className="mt-1 text-sm text-ink-500">Проверка read-only: письма не отправлялись.</p></div></div><span className={`inline-flex shrink-0 items-center justify-center rounded-full px-3 py-1.5 text-xs font-bold ${blocked ? 'bg-rose-100 text-rose-700' : result.status === 'WARNING' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700'}`}>{result.status}</span></div>
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Metric label="Всего контактов" value={result.planned} /><Metric label="Можно отправить" value={result.eligible} tone="green" /><Metric label="Исключено" value={result.excluded} tone={result.excluded ? 'amber' : undefined} /><Metric label="Блокировки" value={result.blocks.length} tone={result.blocks.length ? 'red' : undefined} /></div>
    {result.provider_warning && <div role="status" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" /><div><p className="font-bold">Ограничение провайдера</p><p className="mt-1 leading-6">{result.provider_warning}</p><p className="mt-1 text-xs text-amber-800">Внутренние интервалы и этапы SupplyDesk снижают нагрузку, но не гарантируют доставку или попадание во «Входящие».</p></div></div>}
    {result.budget_warning && <div role="status" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm text-amber-950"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" /><div><p className="font-bold">Ограничение бюджета аккаунта</p><p className="mt-1 leading-6">{result.budget_warning}</p></div></div>}
    {result.blocks.length > 0 && <IssuePanel title="Нужно исправить до запуска" icon={<ShieldAlert className="h-4 w-4" />} tone="red"><ul className="space-y-2">{result.blocks.map((block) => <li key={block} className="flex items-start gap-2 text-sm"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" /><span><span className="font-semibold">{blockLabel(block, result)}</span><span className="ml-1 text-rose-700/80">(код: {block})</span></span></li>)}</ul></IssuePanel>}
    {result.warnings.length > 0 && <IssuePanel title="Предупреждения" icon={<AlertTriangle className="h-4 w-4" />} tone="amber"><ul className="space-y-2">{result.warnings.map((warning) => <li key={warning} className="flex items-start gap-2 text-sm"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" /><span>{warningLabel(warning)} <span className="text-xs text-amber-700/75">({warning})</span></span></li>)}</ul>{result.warnings.includes('high_content_similarity') && <p className="mt-3 border-t border-amber-200 pt-3 text-xs leading-5 text-amber-900">SupplyDesk не будет искусственно менять текст. Если это важно, отредактируйте шаблон вручную.</p>}</IssuePanel>}
    <section className="rounded-xl border border-accent-200 bg-accent-50/50 p-4"><div className="flex items-start gap-3"><input id="manual-stage-approval" type="checkbox" checked={manualStageApproval} onChange={(event) => onManualStageApprovalChange(event.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2" /><div><label htmlFor="manual-stage-approval" className="cursor-pointer text-sm font-bold text-ink-900">Подтверждать каждый этап вручную</label><p className="mt-1 text-xs leading-5 text-ink-600">После каждой партии кампания остановится и покажет результаты. Следующий этап начнётся только после вашего подтверждения.</p></div></div></section>
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,0.8fr)]"><section className="rounded-xl border border-ink-200 bg-white p-4"><div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-bold text-ink-900">Персонализация</h3><p className="mt-1 text-xs leading-5 text-ink-500">Фактические данные поставщика, без случайных изменений текста.</p></div><span className="text-sm font-bold tabular-nums text-ink-700">{Math.round((result.similarity_ratio || 0) * 100)}% похожести</span></div><div className="mt-4 space-y-2">{Object.entries(result.personalization_distribution).sort(([a], [b]) => Number(a) - Number(b)).map(([level, count]) => <div key={level} className="flex items-center gap-3 text-xs"><span className="w-32 shrink-0 text-ink-600">{personalizeLabel(Number(level))}</span><div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-100"><div className="h-full rounded-full bg-accent-500" style={{ width: `${result.eligible ? Math.min(100, (count / result.eligible) * 100) : 0}%` }} /></div><span className="w-7 text-right font-bold tabular-nums text-ink-800">{count}</span></div>)}</div></section><section className="rounded-xl border border-ink-200 bg-ink-50/50 p-4"><h3 className="text-sm font-bold text-ink-900">Оценка запуска</h3><dl className="mt-3 space-y-2.5 text-xs"><div className="flex justify-between gap-3"><dt className="text-ink-500">Провайдер</dt><dd className="font-semibold text-ink-800">{result.provider ?? 'не подключён'}</dd></div><div className="flex justify-between gap-3"><dt className="text-ink-500">Максимум кампании</dt><dd className="font-semibold text-ink-800">{result.campaign_limits.max_recipients}</dd></div><div className="flex justify-between gap-3"><dt className="text-ink-500">Ориентир по времени</dt><dd className="font-semibold text-ink-800">{formatDuration(result.estimated_duration_seconds.average)}</dd></div><p className="text-right text-xs text-ink-500">Диапазон: {formatDurationValue(result.estimated_duration_seconds.minimum)} – {formatDurationValue(result.estimated_duration_seconds.maximum)}</p><div className="flex justify-between gap-3"><dt className="text-ink-500">Этапы</dt><dd className="font-semibold text-ink-800">{rolloutPlan(result)}</dd></div></dl><p className="mt-4 border-t border-ink-200 pt-3 text-xs leading-5 text-ink-500">Режим проверки этапов: <span className="font-semibold text-ink-700">{manualStageApproval ? 'ручное подтверждение' : 'автоматическое продолжение'}</span>.</p></section></div>
    <section className="rounded-xl border border-ink-200 bg-white p-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><h3 className="text-sm font-bold text-ink-900">Точный предпросмотр</h3><p className="mt-1 text-xs leading-5 text-ink-500">Показывает рендер backend для конкретного поставщика.</p></div><button type="button" onClick={onLoadPreview} disabled={previewLoading || blocked} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-ink-200 px-3 text-xs font-bold text-ink-700 hover:border-accent-300 hover:text-accent-700 disabled:cursor-not-allowed disabled:opacity-50">{previewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}{preview ? 'Обновить просмотр' : 'Открыть просмотр'}</button></div>{preview?.previews && preview.previews.length > 0 && <div className="mt-4 grid gap-4 lg:grid-cols-[180px_minmax(0,1fr)]"><div className="flex gap-2 overflow-x-auto pb-1 lg:block lg:space-y-2 lg:overflow-visible">{preview.previews.map((item, index) => <button type="button" key={`${item.to_email}-${index}`} onClick={() => onSelectPreview(index)} className={`min-w-[150px] rounded-lg border px-3 py-2 text-left text-xs transition lg:w-full ${index === previewIndex ? 'border-accent-400 bg-accent-50 text-accent-800' : 'border-ink-200 bg-white text-ink-600 hover:border-accent-300'}`}><span className="block truncate font-bold">{supplierByEmail.get(item.to_email.toLowerCase())?.name ?? item.to_email}</span><span className="mt-1 block truncate text-ink-500">{personalizeLabel(item.personalization_level)}</span></button>)}</div>{currentPreview && <div className="min-w-0 rounded-xl border border-ink-200 bg-ink-50/40 p-4"><dl className="space-y-2 text-xs"><div className="flex flex-col gap-1 sm:flex-row sm:gap-3"><dt className="shrink-0 text-ink-500">Кому</dt><dd className="break-all font-semibold text-ink-800">{currentPreview.to_email}</dd></div><div className="flex flex-col gap-1 sm:flex-row sm:gap-3"><dt className="shrink-0 text-ink-500">Тема</dt><dd className="break-words font-semibold text-ink-800">{currentPreview.subject}</dd></div></dl><div className="mt-4 border-t border-ink-200 pt-4"><p className="whitespace-pre-wrap break-words text-sm leading-6 text-ink-800">{currentPreview.body_text}</p></div><p className="mt-4 text-xs text-ink-500">Персонализация: <span className="font-semibold text-ink-700">{personalizeLabel(currentPreview.personalization_level)}</span></p></div>}</div>}{preview && (!preview.previews || preview.previews.length === 0) && <p className="mt-4 text-sm text-ink-500">Нет eligible-писем для просмотра.</p>}{!preview && <div className="mt-4 flex items-start gap-2 rounded-lg bg-ink-50 px-3 py-3 text-xs leading-5 text-ink-500"><Eye className="mt-0.5 h-4 w-4 shrink-0 text-ink-400" />Предпросмотр не замораживает намерение. Перед запуском SupplyDesk повторит проверку.</div>}</section>
    {excludedRows.length > 0 && <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-4"><div className="flex items-center gap-2"><FileWarning className="h-4 w-4 text-amber-700" /><h3 className="text-sm font-bold text-amber-950">Исключённые получатели · {excludedRows.length}</h3></div><div className="mt-3 overflow-hidden rounded-lg border border-amber-200 bg-white"><div className="hidden grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)] gap-3 border-b border-amber-100 px-3 py-2 text-2xs font-bold uppercase tracking-wider text-amber-800 sm:grid"><span>Поставщик</span><span>Email</span><span>Причина</span></div>{excludedRows.map((recipient) => { const supplier = supplierByEmail.get(recipient.email.toLowerCase()); return <div key={recipient.email} className="grid gap-1 border-b border-amber-100 px-3 py-3 text-xs last:border-b-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)] sm:gap-3"><span className="min-w-0 break-words font-semibold text-ink-800">{supplier?.name ?? 'Контакт без карточки'}</span><span className="min-w-0 break-all text-ink-600">{recipient.email || '—'}</span><span className="min-w-0 break-words text-amber-900">{recipient.reasons.map(reasonLabel).join(', ')}</span></div>; })}</div></section>}
    {!blocked && result.status === 'WARNING' && <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"><input type="checkbox" checked={acknowledgedWarnings} onChange={(event) => onAcknowledgeWarnings(event.target.checked)} className="mt-0.5 h-4 w-4 shrink-0 accent-accent-600" /><span><span className="font-bold">Я проверил предупреждения и хочу продолжить.</span><span className="mt-1 block text-xs leading-5 text-amber-900/80">Проверка не обещает доставку во «Входящие». SupplyDesk не будет искусственно менять текст писем.</span></span></label>}
    {error && <p role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</p>}
    <div className="flex flex-col-reverse gap-2 border-t border-ink-100 pt-4 sm:flex-row sm:items-center sm:justify-between"><button type="button" onClick={onBack} className="inline-flex min-h-10 items-center justify-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-ink-600 hover:bg-ink-50"><ChevronLeft className="h-4 w-4" />Изменить письмо</button>{!blocked && <button type="button" onClick={onContinue} disabled={result.status === 'WARNING' && !acknowledgedWarnings} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-bold text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50">Перейти к запуску<ArrowRight className="h-4 w-4" /></button>}</div>
  </div>;
}

function SelectionSummary({ result }: { result: PreflightResult }) {
  const selection = result.contact_selection;
  const alternates = (result.recipient_results ?? []).filter((item) => item.alternate_selected);
  if (!selection && alternates.length === 0) return null;
  return <section aria-label="Решение по контактам" className="rounded-xl border border-accent-200 bg-accent-50/50 p-4">
    <div className="flex items-start gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent-600" /><div><h3 className="text-sm font-bold text-ink-900">Решение по контактам</h3><p className="mt-1 text-xs leading-5 text-ink-600">На одну выбранную компанию приходится максимум одно письмо. Если основной email уже использован, выбран первый неиспользованный альтернативный.</p></div></div>
    {selection && <>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4"><Metric label="Компаний" value={selection.selected_companies} /><Metric label="Писем будет создано" value={selection.would_create} tone="green" /><Metric label="Уже обращались" value={selection.already_contacted} tone={selection.already_contacted ? 'amber' : undefined} /><Metric label="Альтернативный email" value={selection.alternate_selected} /></div>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4"><Metric label="Есть ответ" value={selection.answered} tone={selection.answered ? 'amber' : undefined} /><Metric label="Нет подходящего email" value={selection.no_eligible_email} tone={selection.no_eligible_email ? 'amber' : undefined} /><Metric label="Ошибки" value={selection.errors} tone={selection.errors ? 'red' : undefined} /><Metric label="Неоднозначные" value={selection.ambiguous} tone={selection.ambiguous ? 'red' : undefined} /></div>
    </>}
    {alternates.length > 0 && <div className="mt-3 space-y-1.5 rounded-lg border border-accent-200 bg-white px-3 py-2.5 text-xs"><p className="font-bold text-ink-800">Выбраны альтернативы</p>{alternates.map((item) => <p key={`${item.requested_email}-${item.email}`} className="break-all text-ink-600"><span className="font-semibold text-ink-800">{item.requested_email}</span> → <span className="font-semibold text-accent-700">{item.email}</span></p>)}</div>}
  </section>;
}

function RepeatControl({ allowRepeat, onChange }: { allowRepeat: boolean; onChange: (value: boolean) => void }) {
  return <section className={`mb-5 rounded-xl border p-4 ${allowRepeat ? 'border-amber-300 bg-amber-50' : 'border-ink-200 bg-ink-50/50'}`}>
    <div className="flex items-start gap-3">
      <input id="allow-repeat" type="checkbox" checked={allowRepeat} onChange={(event) => onChange(event.target.checked)} className="mt-1 h-4 w-4 shrink-0 accent-accent-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2" />
      <div>
        <label htmlFor="allow-repeat" className="cursor-pointer text-sm font-bold text-ink-900">Разрешить явный повтор для уже использованных email</label>
        <p className="mt-1 text-xs leading-5 text-ink-600">По умолчанию уже поставленные, отправленные, ошибочные и неизвестные отправки не повторяются. Включайте этот режим только для осознанного повтора; одна компания всё равно получит не более одного письма за запуск.</p>
      </div>
    </div>
  </section>;
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: 'green' | 'amber' | 'red' }) {
  return <div className="rounded-xl border border-ink-200 bg-white px-3 py-3 shadow-soft"><p className="text-2xs font-semibold leading-4 text-ink-500">{label}</p><p className={`mt-1 text-xl font-bold tabular-nums ${tone === 'green' ? 'text-emerald-700' : tone === 'amber' ? 'text-amber-700' : tone === 'red' ? 'text-rose-700' : 'text-ink-900'}`}>{value}</p></div>;
}

function IssuePanel({ title, icon, tone, children }: { title: string; icon: ReactNode; tone: 'red' | 'amber'; children: ReactNode }) {
  return <section className={`rounded-xl border p-4 ${tone === 'red' ? 'border-rose-200 bg-rose-50/70 text-rose-950' : 'border-amber-200 bg-amber-50/70 text-amber-950'}`}><h3 className="flex items-center gap-2 text-sm font-bold">{icon}{title}</h3><div className="mt-3">{children}</div></section>;
}

function ConfirmationView({ result, manualStageApproval, onBack, onStart, starting, error }: { result: PreflightResult; manualStageApproval: boolean; onBack: () => void; onStart: () => void; starting: boolean; error: string }) {
  return <div className="mx-auto max-w-2xl space-y-5"><div className="rounded-2xl border border-accent-200 bg-accent-50/60 p-5 sm:p-6"><div className="flex items-start gap-3"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-accent-600 shadow-soft"><Send className="h-5 w-5" /></div><div><p className="text-xs font-bold uppercase tracking-[0.14em] text-accent-700">Последняя проверка перед стартом</p><h3 className="mt-1 text-xl font-bold tracking-tight text-ink-900">Будет создана кампания</h3><p className="mt-2 text-sm leading-6 text-ink-600">Отправка начнётся только после ещё одной проверки данных.</p></div></div><dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">{[['Получателей', result.eligible], ['Первый этап', Math.min(result.eligible, result.rollout.stage_1)], ['Интервал', pacingRange(result)], ['Лимит / день', result.account_budget.max_per_day]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-white/80 bg-white/80 px-3 py-3"><dt className="text-xs text-ink-500">{label}</dt><dd className="mt-1 text-sm font-bold text-ink-900">{value}</dd></div>)}</dl><p className="mt-4 rounded-lg border border-accent-200 bg-white/70 px-3 py-2.5 text-sm font-semibold text-ink-800">{manualStageApproval ? 'Этапы подтверждаются вручную.' : 'Этапы продолжаются автоматически при нормальном состоянии кампании.'}</p></div><div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950"><span className="font-bold">Важно:</span> SMTP accepted означает только, что почтовый сервер принял письмо. Это не подтверждает доставку во «Входящие».</div><p className="text-xs leading-5 text-ink-500">Этапы кампании: {result.rollout.stage_1} → {result.rollout.stage_2} → {result.rollout.stage_3} → остальные. Это внутренние настройки SupplyDesk, а не разрешённые лимиты провайдера.</p>{error && <p role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />{error}</p>}<div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><button type="button" onClick={onBack} disabled={starting} className="min-h-10 rounded-lg px-4 text-sm font-semibold text-ink-600 hover:bg-ink-50 disabled:opacity-50">Назад</button><button type="button" onClick={onStart} disabled={starting} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-bold text-white hover:bg-accent-700 disabled:cursor-wait disabled:opacity-50">{starting ? <Loader2 className="h-4 w-4" /> : <Send className="h-4 w-4" />}{starting ? 'Запускаем…' : 'Запустить кампанию'}</button></div></div>;
}
