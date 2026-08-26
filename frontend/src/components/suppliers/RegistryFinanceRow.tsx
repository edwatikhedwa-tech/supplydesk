import { CalendarClock, CircleCheck, CircleX, TrendingDown, TrendingUp } from 'lucide-react';
import { formatFullDate, pluralize } from '@/lib/utils';
import type { GlobalSupplierFinances, GlobalSupplierRegistry } from '@/lib/types';
import checkoIcon from '@/assets/checko-icon.png';

export function companyAgeYears(registeredAt: string): number | null {
  const parsed = Date.parse(registeredAt);
  if (Number.isNaN(parsed)) return null;
  const years = (Date.now() - parsed) / (365.25 * 24 * 60 * 60 * 1000);
  return years >= 0 ? Math.floor(years) : null;
}

function pluralYears(n: number): string {
  return pluralize(n, 'год', 'года', 'лет');
}

/** Checko keeps organisations and sole traders on different paths — verified
 * live 26.08.2026: /company/{ОГРН} → 200, /entrepreneur/{ОГРНИП} → 200, and
 * /company/{ОГРНИП} → 404. An ОГРНИП is 15 digits, an ОГРН 13, so the number
 * itself says which page to open — no extra field needed from the API. */
export const checkoProfileUrl = (ogrn: string) =>
  `https://checko.ru/${ogrn.replace(/\D/g, '').length === 15 ? 'entrepreneur' : 'company'}/${ogrn}`;

function formatRegDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

/** A missing figure is shown as a muted dash, never as 0 — the dash keeps the
 * column aligned while making it obvious the value is unknown, not zero. */
function NoValue() {
  return <span className="text-2xs text-ink-300">—</span>;
}

export function AgeCell({ registry }: { registry: GlobalSupplierRegistry | null | undefined }) {
  const age = registry?.registered_at ? companyAgeYears(registry.registered_at) : null;
  if (age === null || !registry) return <NoValue />;
  return (
    <span className="inline-flex items-baseline gap-1 whitespace-nowrap" title={`Компания зарегистрирована ${formatRegDate(registry.registered_at)}`}>
      <span className="text-sm font-semibold tabular-nums text-ink-800">{age}</span>
      <span className="text-2xs text-ink-400">{pluralYears(age)}</span>
    </span>
  );
}

export function RevenueCell({ finances }: { finances: GlobalSupplierFinances | null | undefined }) {
  if (finances?.revenue == null) return <NoValue />;
  return (
    <span
      className="inline-flex flex-col leading-tight"
      title={`Выручка за ${finances.report_year} год по данным Росстата и ГИР БО (Checko)`}
    >
      <span className="whitespace-nowrap text-sm font-semibold tabular-nums text-ink-800">{formatRubCompact(finances.revenue)} ₽</span>
      <span className="text-[10px] text-ink-400">за {finances.report_year}</span>
    </span>
  );
}

export function ProfitCell({ finances }: { finances: GlobalSupplierFinances | null | undefined }) {
  if (finances?.profit == null) return <NoValue />;
  const loss = finances.profit < 0;
  return (
    <span
      className="inline-flex items-center gap-1 whitespace-nowrap"
      title={`${loss ? 'Убыток' : 'Чистая прибыль'} за ${finances.report_year} год по данным Росстата и ГИР БО (Checko)`}
    >
      {loss ? <TrendingDown className="h-3 w-3 shrink-0 text-rose-500" /> : <TrendingUp className="h-3 w-3 shrink-0 text-emerald-600" />}
      <span className={`text-sm font-semibold tabular-nums ${loss ? 'text-rose-600' : 'text-ink-800'}`}>
        {formatRubCompact(finances.profit)} ₽
      </span>
    </span>
  );
}

export function RegistryStatusCell({ registry }: { registry: GlobalSupplierRegistry | null | undefined }) {
  if (!registry?.status) return <NoValue />;
  const active = registry.is_active;
  return (
    <span
      className={`inline-flex min-w-0 items-center gap-1 ${active ? 'text-emerald-700' : 'text-rose-600'}`}
      title={`${registry.status} — статус в ЕГРЮЛ по данным Checko`}
    >
      {active ? <CircleCheck className="h-3.5 w-3.5 shrink-0" /> : <CircleX className="h-3.5 w-3.5 shrink-0" />}
      <span className="truncate text-2xs font-semibold">{active ? 'Действует' : registry.status}</span>
    </span>
  );
}

export function CheckoLinkCell({ registry }: { registry: GlobalSupplierRegistry | null | undefined }) {
  if (!registry?.ogrn) return <NoValue />;
  return (
    <a
      href={checkoProfileUrl(registry.ogrn)}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
      title="Открыть профиль компании на Checko"
      className="inline-flex h-7 w-7 items-center justify-center rounded-lg opacity-70 transition hover:bg-ink-100 hover:opacity-100"
    >
      <img src={checkoIcon} alt="Checko" className="h-4 w-4 rounded-sm" />
    </a>
  );
}

export function formatRubCompact(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(1).replace(/\.0$/, '')} млрд`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1).replace(/\.0$/, '')} млн`;
  if (abs >= 1_000) return `${sign}${Math.round(abs / 1_000)} тыс`;
  return `${sign}${abs}`;
}

/** Compact single-line Checko registry/finance facts — age, status, revenue,
 * profit, link to the profile page. Shared by both the GlobalSupplier CRM
 * card (suppliers/blacklist) and the per-request supplier panel, so the same
 * ИНН shows the same facts everywhere it's shown. Renders nothing at all
 * when there's no data — never a zero or a fabricated value. */
export function RegistryFinanceRow({
  registry, finances, className = 'px-6 py-2 border-b border-ink-100',
}: {
  registry: GlobalSupplierRegistry | null | undefined;
  finances: GlobalSupplierFinances | null | undefined;
  className?: string;
}) {
  const age = registry?.registered_at ? companyAgeYears(registry.registered_at) : null;
  const hasAnything = age !== null || registry?.status || registry?.ogrn ||
    finances?.revenue != null || finances?.profit != null;
  if (!hasAnything) return null;

  return (
    <div className={`${className} flex items-center gap-3.5 overflow-x-auto`}>
      {age !== null && registry && (
        <div className="flex items-baseline gap-1 shrink-0" title={`Компания зарегистрирована ${formatFullDate(registry.registered_at)}`}>
          <CalendarClock className="w-3.5 h-3.5 text-ink-400 self-center" />
          <span className="text-sm font-bold text-ink-900">{age}</span>
          <span className="text-[10px] text-ink-500">{pluralYears(age)}</span>
        </div>
      )}
      {registry?.status && (
        <div
          className="flex items-center gap-1 shrink-0"
          title={registry.is_active ? 'Действующая организация по данным ЕГРЮЛ (Checko)' : 'Статус по данным ЕГРЮЛ (Checko) — не «действует»'}
        >
          {registry.is_active ? (
            <CircleCheck className="w-3.5 h-3.5 text-emerald-600" />
          ) : (
            <CircleX className="w-3.5 h-3.5 text-red-500" />
          )}
          <span className={`text-sm font-bold whitespace-nowrap ${registry.is_active ? 'text-emerald-700' : 'text-red-600'}`}>
            {registry.status}
          </span>
        </div>
      )}
      {finances?.revenue != null && (
        <div className="flex items-baseline gap-1 shrink-0" title={`Выручка за ${finances.report_year} год (данные Росстата через Checko)`}>
          <TrendingUp className="w-3.5 h-3.5 text-ink-400 self-center" />
          <span className="text-sm font-bold text-ink-900 whitespace-nowrap">{formatRubCompact(finances.revenue)} ₽</span>
          <span className="text-[10px] text-ink-500">выр.</span>
        </div>
      )}
      {finances?.profit != null && (
        <div className="flex items-baseline gap-1 shrink-0" title={`Чистая прибыль за ${finances.report_year} год (данные Росстата через Checko)`}>
          {finances.profit < 0 ? (
            <TrendingDown className="w-3.5 h-3.5 text-red-500 self-center" />
          ) : (
            <TrendingUp className="w-3.5 h-3.5 text-ink-400 self-center" />
          )}
          <span className={`text-sm font-bold whitespace-nowrap ${finances.profit < 0 ? 'text-red-600' : 'text-ink-900'}`}>
            {formatRubCompact(finances.profit)} ₽
          </span>
          <span className="text-[10px] text-ink-500">приб.</span>
        </div>
      )}
      {registry?.ogrn && (
        <a
          href={checkoProfileUrl(registry.ogrn)}
          target="_blank"
          rel="noreferrer"
          className="flex items-center shrink-0 opacity-80 hover:opacity-100 transition-opacity ml-auto pl-1"
          title="Открыть профиль компании на Checko"
        >
          <img src={checkoIcon} alt="Checko" className="w-4 h-4 rounded-sm" />
        </a>
      )}
    </div>
  );
}
