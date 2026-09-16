import { useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { ContactResult } from '../lib/types';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

const RESULT_OPTIONS: { value: ContactResult; label: string }[] = [
  { value: 'not_reached', label: 'Не дозвонился' },
  { value: 'contact_confirmed', label: 'Контакт подтверждён' },
  { value: 'new_email_provided', label: 'Уточнён новый email' },
  { value: 'call_back_later', label: 'Связаться позже' },
  { value: 'supplier_declines', label: 'Поставщик не работает с запросом' },
];

/** "Связаться" outcome form for a `needs_followup` conversation --
 * see docs/ui/MESSAGES_SCREEN_SPEC.md §13a. Saving always records a history
 * event; `new_email_provided` additionally sets an immediate, workspace-only
 * preferred-contact override (never the global card) and reports one
 * (weak) confirmation signal toward the cross-tenant consensus. */
export function ContactResultModal({
  requestId,
  supplierId,
  supplierName,
  onClose,
  onSaved,
}: {
  requestId: number;
  supplierId: number;
  supplierName: string;
  onClose: () => void;
  /** Fired only after the backend has actually confirmed the write --
   * `overrideCreated`/`email` reflect the real API response, never an
   * assumption from which radio option was selected, so a caller can show
   * a "contact updated" confirmation only when it is actually true. */
  onSaved: (info: { overrideCreated: boolean; email: string | null }) => void;
}) {
  const [result, setResult] = useState<ContactResult>('contact_confirmed');
  const [comment, setComment] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setError('');
    if (result === 'new_email_provided' && !newEmail.trim()) {
      setError('Укажите новый email поставщика.');
      return;
    }
    setSaving(true);
    try {
      const trimmedEmail = newEmail.trim();
      const response = await api.recordContactResult(requestId, supplierId, {
        result,
        comment: comment.trim() || undefined,
        new_email: result === 'new_email_provided' ? trimmedEmail : undefined,
      });
      onSaved({ overrideCreated: response.override_created, email: response.override_created ? trimmedEmail : null });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось сохранить результат контакта.');
      setSaving(false);
    }
  }

  return (
    <Modal title={`Связаться: ${supplierName}`} onClose={onClose} width={440}>
      <div className="space-y-3">
        <div className="space-y-1.5">
          {RESULT_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer items-center gap-2 rounded-md border border-border-strong px-3 py-2 text-[12.5px] text-ink hover:bg-surface-hover has-[:checked]:border-accent-border has-[:checked]:bg-accent-subtle"
            >
              <input
                type="radio"
                name="contact-result"
                value={option.value}
                checked={result === option.value}
                onChange={() => setResult(option.value)}
                className="h-3.5 w-3.5 accent-accent"
              />
              {option.label}
            </label>
          ))}
        </div>

        {result === 'new_email_provided' && (
          <input
            autoFocus
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="new-contact@example.com"
            className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        )}

        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Комментарий (необязательно)"
          rows={3}
          className="w-full resize-none rounded-md border border-border-strong bg-surface px-3 py-2 text-[12.5px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
        />

        {error && <p className="text-[12px] text-danger">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" size="sm" onClick={onClose} disabled={saving}>
            Отмена
          </Button>
          <Button variant="primary" size="sm" onClick={() => void save()} disabled={saving}>
            {saving ? 'Сохраняем…' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
