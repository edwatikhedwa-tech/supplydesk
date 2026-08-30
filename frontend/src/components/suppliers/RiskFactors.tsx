import { CircleCheck, ShieldAlert } from 'lucide-react';

/** Факторы риска из ЕГРЮЛ/ЕГРИП — ровно те, что считает сам Checko
 *  (дисквалифицированное лицо в руководстве, массовый руководитель/учредитель,
 *  санкции, банкротство, реестр недобросовестных поставщиков, недоимка по
 *  налогам, массовый/недостоверный адрес — см. checko_client.py:_fill).
 *
 *  Три состояния, не два: `null` — Checko не спрашивали (ИНН ещё не
 *  подтверждён), `[]` — спросили, риска нет, `[...]` — спросили, что-то
 *  нашли. Первое и второе выглядят по-разному нарочно: молчание не должно
 *  читаться как «всё чисто». */

export function RiskCell({ risks }: { risks: string[] | null | undefined }) {
  if (risks == null) return <span className="text-2xs text-ink-300">—</span>;
  if (risks.length === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-emerald-600" title="Checko: факторов риска не найдено">
        <CircleCheck className="h-3.5 w-3.5 shrink-0" />
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-rose-600"
      title={`Факторы риска (Checko):\n${risks.map((r) => `• ${r}`).join('\n')}`}
    >
      <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
      <span className="text-2xs font-semibold tabular-nums">{risks.length}</span>
    </span>
  );
}

export function RiskList({ risks }: { risks: string[] | null | undefined }) {
  if (risks == null) return null;
  if (risks.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
        <CircleCheck className="h-4 w-4 shrink-0" />
        Checko не нашёл факторов риска по данным ЕГРЮЛ/ЕГРИП.
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-700">
        <ShieldAlert className="h-4 w-4 shrink-0" />
        Факторы риска ({risks.length})
      </div>
      <ul className="mt-1.5 space-y-1 text-xs text-rose-700">
        {risks.map((r) => (
          <li key={r} className="flex gap-1.5">
            <span className="text-rose-400">•</span>
            <span>{r}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
