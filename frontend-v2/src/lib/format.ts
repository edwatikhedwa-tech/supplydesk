/** Real current time — this app now reads live data, not fixture-era dates. */
export function now(): Date {
  return new Date();
}

const DAY_MS = 24 * 60 * 60 * 1000;

export function daysFromToday(iso: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso.length <= 10 ? iso + 'T00:00:00+03:00' : iso);
  // Compare calendar days, not the exact time-of-day -- a deadline anchored
  // at midnight would otherwise read as "overdue" the moment any time has
  // passed since midnight on its own day.
  const today = new Date(now().toISOString().slice(0, 10) + 'T00:00:00+03:00');
  return Math.round((d.getTime() - today.getTime()) / DAY_MS);
}

export type DeadlineUrgency = 'overdue' | 'today' | 'soon' | 'normal' | 'none';

export function deadlineUrgency(iso: string | null): DeadlineUrgency {
  const days = daysFromToday(iso);
  if (days === null) return 'none';
  if (days < 0) return 'overdue';
  if (days === 0) return 'today';
  if (days <= 3) return 'soon';
  return 'normal';
}

export function formatDeadline(iso: string | null): string {
  if (!iso) return 'Без срока';
  const days = daysFromToday(iso);
  const date = new Date(iso.length <= 10 ? iso + 'T00:00:00+03:00' : iso);
  const formatted = date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
  if (days === 0) return `Сегодня, ${formatted}`;
  if (days === 1) return `Завтра, ${formatted}`;
  if (days !== null && days < 0) return `Просрочено на ${Math.abs(days)} дн · ${formatted}`;
  return formatted;
}

export function formatRelativeTime(iso: string | null): string {
  if (!iso) return '—';
  const then = new Date(iso);
  const diffMs = now().getTime() - then.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return 'только что';
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr} ч назад`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay === 1) return 'вчера';
  if (diffDay < 7) return `${diffDay} дн назад`;
  return then.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short' });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

/** Compact file size for attachment lists: "480 КБ", "3.2 МБ". */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(/\.0$/, '')} МБ`;
}

/** Compact RUB amount for supplier finance figures: "15.4 млн ₽", "290 тыс ₽". */
export function formatMoney(value: number | null): string {
  if (value === null) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1).replace(/\.0$/, '')} млн ₽`;
  if (abs >= 1_000) return `${sign}${Math.round(abs / 1_000)} тыс ₽`;
  return `${sign}${Math.round(abs)} ₽`;
}

function pluralYears(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `${n} год`;
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return `${n} года`;
  return `${n} лет`;
}

/** Company age from its registry registration date -- an ОГРН-backed signal
 * of how established a supplier is, shown alongside revenue/profit. */
export function companyAge(registeredAt: string | null | undefined): string | null {
  if (!registeredAt) return null;
  const years = now().getFullYear() - new Date(registeredAt).getFullYear();
  return years >= 0 ? pluralYears(years) : null;
}

/** Checko keeps organisations and sole traders on different paths --
 * /company/{ОГРН} for legal entities, /entrepreneur/{ОГРНИП} for sole
 * traders; /company/{ОГРНИП} 404s. An ОГРНИП is 15 digits, an ОГРН 13, so
 * the number itself says which page to open -- no extra field needed. */
export function checkoUrl(ogrn: string | null | undefined): string | null {
  if (!ogrn) return null;
  const isEntrepreneur = ogrn.replace(/\D/g, '').length === 15;
  return `https://checko.ru/${isEntrepreneur ? 'entrepreneur' : 'company'}/${ogrn}`;
}

const LEGAL_FORM_ABBREVIATIONS: [RegExp, string][] = [
  [/ОБЩЕСТВО\s+С\s+ОГРАНИЧЕННОЙ\s+ОТВЕТСТВЕННОСТЬЮ/gi, 'ООО'],
  [/ПУБЛИЧНОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО/gi, 'ПАО'],
  [/ЗАКРЫТОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО/gi, 'ЗАО'],
  [/ОТКРЫТОЕ\s+АКЦИОНЕРНОЕ\s+ОБЩЕСТВО/gi, 'ОАО'],
  [/АКЦИОНЕРНОЕ\s+ОБЩЕСТВО/gi, 'АО'],
  [/ИНДИВИДУАЛЬНЫЙ\s+ПРЕДПРИНИМАТЕЛЬ/gi, 'ИП'],
];

/** "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "РАМ"" -> "ООО «РАМ»" — the
 * full legal form is correct on a requisites/documents page, but reads as
 * noise in a list of company names next to a person's name. */
export function formatCompanyName(name: string): string {
  let result = name;
  for (const [pattern, abbreviation] of LEGAL_FORM_ABBREVIATIONS) {
    result = result.replace(pattern, abbreviation);
  }
  return result.replace(/"([^"]+)"/g, '«$1»').trim();
}

export function initials(name: string): string {
  const parts = name.replace(/[«»"]/g, '').split(/\s+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((p) => p[0]?.toUpperCase() ?? '');
  return letters.join('') || '?';
}
