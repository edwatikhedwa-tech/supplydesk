import { AlertTriangle, CheckCircle2, Send, ShieldCheck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { PreflightResult, SupplierSendInput } from '../lib/types';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

const statusMeta: Record<PreflightResult['status'], { label: string; className: string }> = {
  PASS: { label: 'Можно отправлять', className: 'text-success' },
  WARNING: { label: 'Есть замечания', className: 'text-warning' },
  BLOCK: { label: 'Отправка заблокирована', className: 'text-danger' },
};

/** "Написать" bulk-compose over the recipients selected in a request's
 * supplier list. Reuses the real send pipeline the legacy frontend already
 * uses (frontend/src/components/Composer.tsx): a preflight check must run
 * and come back non-BLOCK before Send is enabled -- this is the same
 * duplicate/invalid-recipient guard that pipeline has always had, not a new
 * restriction invented for this port. */
export function BulkComposeModal({
  requestId,
  recipients,
  onClose,
  onSent,
}: {
  requestId: number;
  recipients: SupplierSendInput[];
  onClose: () => void;
  onSent: () => void;
}) {
  const [subject, setSubject] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [templateLoading, setTemplateLoading] = useState(true);
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState<number | null>(null);

  useEffect(() => {
    api
      .mailTemplate()
      .then((t) => {
        setSubject(t.subject);
        setBodyText(t.body);
      })
      .catch(() => setError('Не удалось загрузить шаблон письма — заполните тему и текст вручную.'))
      .finally(() => setTemplateLoading(false));
  }, []);

  function edited() {
    setPreflight(null);
  }

  async function runPreflight() {
    setChecking(true);
    setError('');
    try {
      const result = await api.preflightBulk({ request_id: requestId, suppliers: recipients, subject, body_text: bodyText });
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
      const result = await api.sendMailBulk({ request_id: requestId, suppliers: recipients, subject, body_text: bodyText, idempotency_key: idempotencyKey });
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

  const canSend = preflight !== null && preflight.status !== 'BLOCK' && !sending;

  return (
    <Modal title={`Написать ${recipients.length} поставщик${recipients.length === 1 ? 'у' : 'ам'}`} onClose={onClose} width={560}>
      <div className="flex flex-col gap-3">
        <div className="max-h-[80px] overflow-y-auto rounded-md border border-border-strong bg-canvas px-2.5 py-1.5 text-[11.5px] text-ink-muted">
          {recipients.map((r) => r.name || r.email).join(', ')}
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-medium text-ink-faint">Тема письма</label>
          <input
            value={subject}
            onChange={(e) => {
              setSubject(e.target.value);
              edited();
            }}
            disabled={templateLoading}
            className="h-8 w-full rounded-md border border-border-strong bg-surface px-2.5 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>

        <div>
          <label className="mb-1 block text-[11px] font-medium text-ink-faint">Текст письма</label>
          <textarea
            value={bodyText}
            onChange={(e) => {
              setBodyText(e.target.value);
              edited();
            }}
            disabled={templateLoading}
            rows={8}
            className="w-full resize-y rounded-md border border-border-strong bg-surface px-2.5 py-2 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
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
          <Button variant="secondary" size="sm" icon={<ShieldCheck size={13} />} disabled={checking || templateLoading || !subject.trim() || !bodyText.trim()} onClick={() => void runPreflight()}>
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
