function parseDate(dateStr: string | null): Date | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Compare calendar dates in the browser's local timezone, not elapsed 24-hour
 * periods. This keeps a message received yesterday at 23:50 from becoming
 * "Сегодня" after midnight, and keeps the list and detail views consistent.
 */
function calendarDayDelta(from: Date, to: Date): number {
  const fromDay = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const toDay = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((fromDay - toDay) / 86400000);
}

function formatClock(date: Date): string {
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

export function formatRelativeDate(dateStr: string | null): string {
  const date = parseDate(dateStr);
  if (!date) return '';
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const dayDelta = calendarDayDelta(now, date);

  if (diffMin >= 0 && diffMin < 1) return 'только что';
  if (diffMin >= 0 && diffMin < 60) return `${diffMin} мин назад`;
  if (dayDelta === 0) return `Сегодня ${formatClock(date)}`;
  if (dayDelta === 1) return `Вчера ${formatClock(date)}`;
  if (dayDelta > 1 && dayDelta < 7) return `${dayDelta} дн назад`;
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' });
}

export function formatFullDate(dateStr: string | null): string {
  const date = parseDate(dateStr);
  if (!date) return '';
  const now = new Date();
  const dayDelta = calendarDayDelta(now, date);
  const time = formatClock(date);

  if (dayDelta === 0) return `Сегодня, ${time}`;
  if (dayDelta === 1) return `Вчера, ${time}`;
  if (dayDelta > 0 && dayDelta < 365) {
    return `${date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}, ${time}`;
  }
  return `${date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}, ${time}`;
}

export function getInitials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '?';
  const parts = trimmed.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return trimmed.slice(0, 2).toUpperCase();
}

export function getAvatarColor(name: string): string {
  const colors = [
    'bg-blue-100 text-blue-700',
    'bg-emerald-100 text-emerald-700',
    'bg-amber-100 text-amber-700',
    'bg-rose-100 text-rose-700',
    'bg-cyan-100 text-cyan-700',
    'bg-indigo-100 text-indigo-700',
    'bg-teal-100 text-teal-700',
    'bg-orange-100 text-orange-700',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ');
}

/** Russian plural forms: pluralize(1,'поставщик','поставщика','поставщиков') -> 'поставщик'. */
export function pluralize(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if ([2, 3, 4].includes(mod10) && ![12, 13, 14].includes(mod100)) return few;
  return many;
}

// Full legal forms (as they appear verbatim in ЕГРЮЛ/ЕГРИП exports) mapped to
// the short abbreviation everyone actually reads. Longest form first so
// "ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО" doesn't get caught by a shorter substring.
const LEGAL_FORM_ABBREVIATIONS: [RegExp, string][] = [
  [/^ЗАКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО\s+/i, 'ЗАО '],
  [/^ОТКРЫТОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО\s+/i, 'ОАО '],
  [/^ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО\s+/i, 'ПАО '],
  [/^АКЦИОНЕРНОЕ ОБЩЕСТВО\s+/i, 'АО '],
  [/^ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ\s+/i, 'ООО '],
  [/^ИНДИВИДУАЛЬНЫЙ ПРЕДПРИНИМАТЕЛЬ\s+/i, 'ИП '],
];

/** "ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "АТЛАНТ"" -> "ООО "АТЛАНТ"" — full
 * form is still the real legal name, so keep it available for a `title` tooltip
 * rather than throwing it away. */
function shortCompanyName(name: string): string {
  const trimmed = name.trim();
  for (const [pattern, short] of LEGAL_FORM_ABBREVIATIONS) {
    if (pattern.test(trimmed)) return trimmed.replace(pattern, short);
  }
  return trimmed;
}

/** A 12-digit ИНН belongs to a person — a sole trader (ИП) or a self-employed
 * individual. Organisations always have 10. */
function isSoleTrader(inn: string): boolean {
  return inn.replace(/\D/g, '').length === 12;
}

/** Checko returns a sole trader's registry name as a bare "Фамилия Имя
 * Отчество" — indistinguishable from a random person's name in a list of
 * companies. Show it the way a buyer would write it: "ИП Опрышко С. А.".
 * Anything that isn't a plain three-word ФИО is left alone rather than
 * mangled. */
export function displaySupplierName(name: string, inn: string): string {
  const trimmed = name.trim();
  if (!isSoleTrader(inn) || /^ИП\s/i.test(trimmed)) return shortCompanyName(trimmed);
  const parts = trimmed.split(/\s+/);
  if (parts.length === 3 && parts.every((p) => /^[А-ЯЁ][а-яё-]+$/.test(p))) {
    const [last, first, middle] = parts;
    return `ИП ${last} ${first[0]}. ${middle[0]}.`;
  }
  return shortCompanyName(trimmed);
}

/** Shorten legal prefixes in correspondence rows while keeping ИП intact.
 * The complete legal name remains available through the element title. */
export function displayCorrespondenceSupplierName(name: string): string {
  const trimmed = name.trim();
  if (!trimmed || /^ИП\b/i.test(trimmed)) return trimmed;
  for (const [pattern, short] of LEGAL_FORM_ABBREVIATIONS) {
    if (pattern.test(trimmed)) return trimmed.replace(pattern, short);
  }
  return trimmed;
}
