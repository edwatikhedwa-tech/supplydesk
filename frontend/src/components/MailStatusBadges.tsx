import type { Supplier } from '@/lib/types';
import { DELIVERY_META, deliveryCountsFor, responseStatusFor } from '@/useRequestState';

interface Props {
  supplier: Supplier;
  onOpenThread?: (id: number) => void;
  compact?: boolean;
}

const DELIVERY_ORDER = ['bounced', 'failed', 'delivery_unknown', 'queued', 'accepted', 'cancelled', 'not_sent'] as const;

function DeliveryBadge({ status, count }: { status: typeof DELIVERY_ORDER[number]; count: number }) {
  const meta = DELIVERY_META[status];
  return (
    <span title={meta.title} className={`inline-flex w-fit max-w-full items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-2xs font-semibold ring-1 ${meta.badge}`}>
      <span>{meta.icon}</span>{meta.label}{count > 1 && <span className="tabular-nums opacity-70">· {count}</span>}
    </span>
  );
}

export function MailStatusBadges({ supplier, onOpenThread, compact = false }: Props) {
  const counts = deliveryCountsFor(supplier);
  const response = responseStatusFor(supplier);
  const statuses = DELIVERY_ORDER.filter((status) => counts[status] > 0);
  const showNotSent = statuses.length === 1 && statuses[0] === 'not_sent';
  const visibleStatuses = statuses.filter((status) => status !== 'not_sent');
  const unread = (supplier.unread_count ?? 0) > 0;

  return (
    <div className={`flex min-w-0 flex-wrap items-center gap-1.5 ${compact ? '' : 'gap-y-1'}`}>
      {response === 'answered' && onOpenThread ? (
        <button
          type="button"
          onClick={(event) => { event.stopPropagation(); onOpenThread(supplier.id); }}
          title={unread ? 'Открыть непрочитанный ответ' : 'Открыть переписку'}
          className={`inline-flex w-fit max-w-full items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-2xs font-semibold ring-1 ${unread ? 'bg-emerald-50 text-emerald-700 ring-emerald-200 hover:bg-emerald-100' : 'bg-accent-50 text-accent-700 ring-accent-200 hover:bg-accent-100'}`}
        >
          <span>{unread ? '●' : '✓'}</span>Получен ответ
        </button>
      ) : response === 'answered' ? (
        <span className="inline-flex w-fit max-w-full items-center gap-1 whitespace-nowrap rounded-full bg-emerald-50 px-2 py-0.5 text-2xs font-semibold text-emerald-700 ring-1 ring-emerald-200"><span>✓</span>Получен ответ</span>
      ) : response === 'waiting' ? (
        <span className="inline-flex w-fit max-w-full items-center gap-1 whitespace-nowrap rounded-full bg-amber-50 px-2 py-0.5 text-2xs font-semibold text-amber-700 ring-1 ring-amber-200"><span>◷</span>Ждём ответа</span>
      ) : null}
      {visibleStatuses.map((status) => <DeliveryBadge key={status} status={status} count={counts[status]} />)}
      {showNotSent && <DeliveryBadge status="not_sent" count={counts.not_sent} />}
      {!showNotSent && counts.not_sent > 0 && <span className="text-2xs text-ink-400">ещё {counts.not_sent} контактов не отправляли</span>}
    </div>
  );
}
