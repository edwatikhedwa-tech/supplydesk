import { Check } from 'lucide-react';
import { useEffect } from 'react';

/**
 * Short-lived confirmation shown after "Связаться" -> "Уточнён новый
 * email" -> "Сохранить" actually persists a workspace-preferred override.
 * Never rendered on a guess -- the caller only mounts this once the
 * backend's own response confirmed `override_created: true` (see
 * ContactResultModal.onSaved), so the claim here is always true.
 * Same short-lived fixed-position pattern as TaskCreatedNotice.
 */
export function ContactUpdatedNotice({ email, onDismiss }: { email: string; onDismiss: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onDismiss, 6000);
    return () => window.clearTimeout(timer);
  }, [onDismiss, email]);

  return (
    <div
      role="status"
      className="fixed bottom-4 left-4 right-4 z-50 flex max-w-lg items-start gap-2 rounded-md border border-success-border bg-success-subtle px-3 py-2 text-[12px] text-ink shadow-lg sm:left-auto"
    >
      <Check size={14} className="mt-0.5 shrink-0 text-success" aria-hidden="true" />
      <span>
        Контакт обновлён. Следующие новые запросы этому поставщику будут использовать <span className="font-medium">{email}</span>.
      </span>
    </div>
  );
}
