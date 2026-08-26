import { Ban, Star } from 'lucide-react';
import type { RelationshipStatus } from '@/lib/types';

export function RelationshipBadge({ status }: { status: RelationshipStatus }) {
  if (status === 'none') return <span className="text-xs text-ink-400">—</span>;
  if (status === 'favorite')
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
        <Star className="w-3 h-3" fill="currentColor" />
        Избранный
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
      <Ban className="w-3 h-3" />
      В чёрном списке
    </span>
  );
}

/** Role comes from the supplier's primary ОКВЭД via checko_client.classify_okved
 * — not a guess. For a buyer this is the difference between the factory and a
 * reseller marking it up, so «производитель» is the one that gets colour;
 * everything else stays neutral so it doesn't compete for attention. */
const ROLE_STYLES: Record<string, string> = {
  'производитель': 'bg-emerald-50 text-emerald-700 ring-emerald-200/70',
  'оптовик': 'bg-ink-100 text-ink-600 ring-ink-200/70',
  'розница': 'bg-ink-100 text-ink-500 ring-ink-200/70',
  'подрядчик': 'bg-ink-100 text-ink-600 ring-ink-200/70',
};

export function RoleBadge({ role }: { role?: string | null }) {
  if (!role || role === 'прочее') return null;
  const style = ROLE_STYLES[role] ?? 'bg-ink-100 text-ink-600 ring-ink-200/70';
  return (
    <span
      title={`Роль в цепочке поставок определена по основному коду ОКВЭД (данные ЕГРЮЛ)`}
      className={`shrink-0 whitespace-nowrap rounded-full px-1.5 py-px text-2xs font-semibold ring-1 ${style}`}
    >
      {role}
    </span>
  );
}

export function StarRating({ rating, onChange }: { rating: number; onChange?: (n: number) => void }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          onClick={onChange ? (e) => { e.stopPropagation(); onChange(n); } : undefined}
          disabled={!onChange}
          className={onChange ? 'cursor-pointer hover:scale-110 transition-transform' : 'cursor-default'}
        >
          <Star className={`w-3.5 h-3.5 ${n <= rating ? 'text-amber-400' : 'text-ink-200'}`} fill={n <= rating ? 'currentColor' : 'none'} />
        </button>
      ))}
    </div>
  );
}

export const outcomeLabels: Record<string, string> = {
  not_sent: 'Не отправлен',
  sent: 'Отправлен',
  waiting: 'Ждём ответа',
  answered: 'Ответ получен',
  error: 'Ошибка отправки',
};

export const issueReasonLabels: Record<string, string> = {
  wrong_details: 'Неверный ИНН/реквизиты',
  email_invalid: 'Письмо не доставляется',
  no_response: 'Не отвечает долгое время',
  closed: 'Прекратила деятельность',
  other: 'Другое',
};
