import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';
import { cn } from '../../lib/cn';
import type { ConversationStatus } from '../../lib/types';

/**
 * These are operator workflow states for a supplier conversation. They must
 * not be confused with delivery states such as "Есть ответ" / "Ждём ответа".
 */
const LABEL: Record<ConversationStatus | 'none', string> = {
  none: 'Без статуса',
  in_progress: 'В работе',
  deferred: 'Отложено',
  rejected: 'Отклонено',
};
const PILL_CLASS: Record<ConversationStatus | 'none', string> = {
  none: 'bg-surface-hover text-ink-muted',
  // Green is reserved for the factual delivery state "Есть ответ".
  // The operator's next action should be visually distinct from that fact.
  in_progress: 'bg-accent-subtle text-accent',
  deferred: 'bg-warning-subtle text-warning',
  rejected: 'bg-danger-subtle text-danger',
};
const ORDER: (ConversationStatus | 'none')[] = ['none', 'in_progress', 'deferred', 'rejected'];

function StatusPill({ status }: { status: ConversationStatus | 'none' }) {
  return <span className={cn('inline-flex h-5 w-20 shrink-0 items-center justify-center rounded-md px-1.5 text-[10px] font-medium leading-none whitespace-nowrap', PILL_CLASS[status])}>{LABEL[status]}</span>;
}

/**
 * ReUI's c-select-19 composition, adapted to SupplyDesk's existing Radix
 * Select and status vocabulary: a visible label, a rectangular status badge
 * in the trigger, and the same badges in the option list.
 */
export function ConversationStatusSelect({
 value,
 onChange,
 size = 'default',
  showLabel = true,
 ariaLabel,
 onClick,
}: {
  value: ConversationStatus | null;
  onChange: (v: ConversationStatus | null) => void;
  size?: 'sm' | 'default';
  showLabel?: boolean;
  ariaLabel: string;
  onClick?: (e: React.MouseEvent) => void;
}) {
  const key = value ?? 'none';
  return (
    <Select value={key} onValueChange={(v) => onChange(v === 'none' ? null : (v as ConversationStatus))}>
      <SelectTrigger
        size={size}
        aria-label={ariaLabel}
        onClick={onClick}
        className={cn(
          'border-border-strong bg-surface px-2.5 shadow-none hover:bg-surface-hover',
          size === 'sm' && showLabel
            ? 'min-w-[152px] gap-1.5 text-[11px]'
            : size === 'sm'
              ? 'h-8 w-[116px] shrink-0 justify-between gap-1 rounded-[10px] border-border-strong bg-surface px-2 text-[11px] hover:bg-surface-hover'
              : 'h-8 w-[200px] rounded-[10px] gap-1.5 text-sm',
        )}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          {showLabel && <span className="shrink-0 font-medium text-ink">Статус:</span>}
          <SelectValue>
            <StatusPill status={key} />
          </SelectValue>
        </span>
      </SelectTrigger>
      <SelectContent
        align={size === 'sm' && !showLabel ? 'end' : 'start'}
        className={size === 'sm' && !showLabel ? 'min-w-[132px]' : undefined}
      >
        {ORDER.map((k) => (
          <SelectItem key={k} value={k}>
            <StatusPill status={k} />
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
