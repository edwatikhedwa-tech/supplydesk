import { AlertTriangle, CheckCircle2, Paperclip, Send, ShieldCheck, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { MailAttachment, PreflightResult, SupplierSendInput } from '../lib/types';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

const statusMeta: Record<PreflightResult['status'], { label: string; className: string }> = {
  PASS: { label: 'Можно отправлять', className: 'text-success' },
  WARNING: { label: 'Есть замечания', className: 'text-warning' },
  BLOCK: { label: 'Отправка заблокирована', className: 'text-danger' },
};

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_BYTES = 20 * 1024 * 1024;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function fileToAttachment(file: File): Promise<MailAttachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.slice(result.indexOf(',') + 1);
      resolve({ filename: file.name, mime_type: file.type || 'application/octet-stream', size: file.size, content_base64: base64 });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** "Написать" bulk-compose over the recipients selected in a request's
 * supplier list. Reuses the real send pipeline the legacy frontend already
 * uses (frontend/src/components/Composer.tsx): a preflight check must run
 * and come back non-BLOCK before Send is enabled -- this is the same
 * duplicate/invalid-recipient guard that pipeline has always had, not a new
 * restriction invented for this port. */
export function BulkComposeModal({
  requestId,
  recipients: initialRecipients,
  onClose,
  onSent,
}: {
  requestId: number;
  recipients: SupplierSendInput[];
  onClose: () => void;
  onSent: () => void;
}) {
  const [recipients, setRecipients] = useState(initialRecipients);
  const [subject, setSubject] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [attachments, setAttachments] = useState<MailAttachment[]>([]);
  const [attachError, setAttachError] = useState('');
  const [templateLoading, setTemplateLoading] = useState(true);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .mailTemplate()
      .then((t) => {
        setSubject(t.subject);
        setBodyText(t.body);
        setAttachments(t.attachments ?? []);
      })
      .catch(() => setError('Не удалось загрузить шаблон письма — заполните тему и текст вручную.'))
      .finally(() => setTemplateLoading(false));
  }, []);

  function edited() {
    setPreflight(null);
  }

  function removeRecipient(email: string) {
    setRecipients((prev) => prev.filter((r) => r.email !== email));
    edited();
  }

  async function addFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setAttachError('');
    const currentTotal = attachments.reduce((s, a) => s + (a.size ?? 0), 0);
    let runningTotal = currentTotal;
    const next: MailAttachment[] = [];
    for (const file of Array.from(files)) {
      if (file.size > MAX_FILE_BYTES) {
        setAttachError(`«${file.name}» больше 10 МБ — не прикреплён.`);
        continue;
      }
      if (runningTotal + file.size > MAX_TOTAL_BYTES) {
        setAttachError('Суммарный размер вложений превысил бы 20 МБ — остальные файлы не прикреплены.');
        break;
      }
      try {
        next.push(await fileToAttachment(file));
        runningTotal += file.size;
      } catch {
        setAttachError(`Не удалось прочитать «${file.name}».`);
      }
    }
    if (next.length > 0) {
      setAttachments((prev) => [...prev, ...next]);
      edited();
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
    edited();
  }

  async function runPreflight() {
    setChecking(true);
    setError('');
    try {
      const result = await api.preflightBulk({ request_id: requestId, suppliers: recipients, subject, body_text: bodyText, attachments });
      setPreflight(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось проверить рассылку.');
    } finally {
      setChecking(false);
    }
  }

  async function send() {
    setSending(true);
    setError('');
    try {
      const idempotencyKey = crypto.randomUUID();
      const result = await api.sendMailBulk({
        request_id: requestId,
        suppliers: recipients,
        subject,
        body_text: bodyText,
        attachments,
        idempotency_key: idempotencyKey,
      });
      setDone(result.queued.length);
      onSent();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось поставить письма в очередь на отправку.');
    } finally {
      setSending(false);
    }
  }

  if (done !== null) {
    return (
      <Modal title="Письма поставлены в очередь" onClose={onClose} width={440}>
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          <CheckCircle2 size={32} className="text-success" />
          <p className="text-[13px] text-ink">
            {done} {done === 1 ? 'письмо поставлено' : 'писем поставлено'} в очередь на отправку.
          </p>
          <Button variant="primary" size="sm" onClick={onClose}>
            Готово
          </Button>
        </div>
      </Modal>
    );
  }

  const canSend = recipients.length > 0 && preflight !== null && preflight.status !== 'BLOCK' && !sending;
  const totalAttachedBytes = attachments.reduce((s, a) => s + (a.size ?? 0), 0);

  return (
    <Modal title={`Написать ${recipients.length} поставщик${recipients.length === 1 ? 'у' : recipients.length < 5 ? 'ам' : 'ам'}`} onClose={onClose} width={680}>
      <div className="flex flex-col gap-4">
        <div>
          <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-ink-faint">Получатели</label>
          <div className="flex max-h-[96px] flex-wrap gap-1.5 overflow-y-auto rounded-md border border-border-strong bg-canvas p-2">
            {recipients.length === 0 && <span className="text-[12px] text-ink-faint">Никого не выбрано</span>}
            {recipients.map((r) => (
              <span key={r.email} className="flex items-center gap-1.5 rounded-full border border-border-strong bg-surface py-1 pl-2.5 pr-1.5 text-[12px] text-ink-soft">
                {r.name || r.email}
                <button
                  type="button"
                  onClick={() => removeRecipient(r.email)}
                  aria-label={`Убрать ${r.name || r.email}`}
                  className="flex h-4 w-4 items-center justify-center rounded-full text-ink-faint hover:bg-danger-subtle hover:text-danger"
                >
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-ink-faint">Тема письма</label>
          <input
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              edited();
            }}
            disabled={templateLoading}
            placeholder="Тема письма…"
            className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-ink-faint">Текст письма</label>
          <textarea
            value={bodyText}
            onChange={(e) => {
              setBodyText(e.target.value);
              edited();
            }}
            disabled={templateLoading}
            rows={10}
            placeholder="Текст письма…"
            className="w-full resize-y rounded-md border border-border-strong bg-surface px-3 py-2.5 text-[13px] leading-relaxed outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>

        <div>
          <div className="flex items-center justify-between">
            <label className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">Вложения</label>
            <span className="text-[10.5px] text-ink-faint">
              {formatSize(totalAttachedBytes)} / 20 МБ · до 10 МБ на файл
            </span>
          </div>
          {attachments.length > 0 && (
            <div className="mt-1.5 flex flex-col gap-1">
              {attachments.map((a, i) => (
                <div key={`${a.filename}-${i}`} className="flex items-center gap-2 rounded-md border border-border-strong bg-canvas px-2.5 py-1.5 text-[12px]">
                  <Paperclip size={12} className="shrink-0 text-ink-faint" />
                  <span className="min-w-0 flex-1 truncate text-ink-soft">{a.filename}</span>
                  <span className="shrink-0 text-ink-faint">{a.size ? formatSize(a.size) : ''}</span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(i)}
                    aria-label={`Удалить ${a.filename}`}
                    className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-danger-subtle hover:text-danger"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <input ref={fileInputRef} type="file" multiple hidden onChange={(e) => void addFiles(e.target.files)} />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="mt-1.5 flex h-8 items-center gap-1.5 rounded-md border border-dashed border-border-strong px-2.5 text-[12px] text-ink-muted hover:border-accent hover:text-accent"
          >
            <Paperclip size={13} /> Прикрепить файлы
          </button>
          {attachError && <p className="mt-1 text-[11.5px] text-danger">{attachError}</p>}
        </div>

        {error && <p className="text-[12px] text-danger">{error}</p>}

        {preflight && (
          <div className="rounded-md border border-border-strong bg-canvas px-3 py-2.5 text-[12px]">
            <div className={`flex items-center gap-1.5 font-medium ${statusMeta[preflight.status].className}`}>
              {preflight.status === 'BLOCK' ? <AlertTriangle size={13} /> : <ShieldCheck size={13} />}
              {statusMeta[preflight.status].label}
            </div>
            <p className="mt-1 text-ink-muted">
              Будет отправлено: {preflight.eligible} из {preflight.planned}
              {preflight.excluded > 0 && <span className="text-warning"> · исключено: {preflight.excluded}</span>}
            </p>
            {preflight.recipient_results.some((r) => r.status === 'excluded') && (
              <ul className="mt-1.5 space-y-0.5 text-[11px] text-ink-faint">
                {preflight.recipient_results
                  .filter((r) => r.status === 'excluded')
                  .slice(0, 6)
                  .map((r) => (
                    <li key={r.email}>
                      {r.email} — {r.reasons.join(', ') || 'исключён'}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={sending}>
            Отмена
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<ShieldCheck size={13} />}
            disabled={checking || templateLoading || recipients.length === 0 || !subject.trim() || !bodyText.trim()}
            onClick={() => void runPreflight()}
          >
            {checking ? 'Проверяем…' : 'Проверить рассылку'}
          </Button>
          <Button variant="primary" size="sm" icon={<Send size={13} />} disabled={!canSend} onClick={() => void send()}>
            {sending ? 'Отправляем…' : 'Отправить'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
