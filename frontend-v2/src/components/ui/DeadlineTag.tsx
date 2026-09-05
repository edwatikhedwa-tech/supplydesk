import { deadlineUrgency, formatDeadline } from '../../lib/format';
import { Badge, type Tone } from './Badge';

const urgencyTone: Record<ReturnType<typeof deadlineUrgency>, Tone> = {
  overdue: 'danger',
  today: 'danger',
  soon: 'warning',
  normal: 'neutral',
  none: 'neutral',
};

export function DeadlineTag({ deadline }: { deadline: string | null }) {
  const urgency = deadlineUrgency(deadline);
  if (urgency === 'none') {
    return <span className="text-ink-faint">Без срока</span>;
  }
  return (
    <Badge tone={urgencyTone[urgency]} dot={urgency === 'overdue' || urgency === 'today'}>
      {formatDeadline(deadline)}
    </Badge>
  );
}
