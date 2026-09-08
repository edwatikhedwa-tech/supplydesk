import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatMoney } from '../lib/format';
import type { GlobalSupplierFinanceYear } from '../lib/types';

/** Динамика выручки и прибыли по годам -- направление важнее абсолютной
 * цифры для закупщика: "выручка растёт, прибыль падает" -- повод спросить
 * про условия оплаты; число одного года такого не покажет, форма покажет.
 * Same read as the legacy frontend's FinanceTrend.tsx, rebuilt on Recharts
 * (already a dependency there) instead of hand-rolled SVG -- a dual-axis
 * bar+line combo is exactly the kind of chart that's easy to get subtly
 * wrong by hand. */

function axisTick(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${Math.round(value / 1_000_000_000)} млрд`;
  if (abs >= 1_000_000) return `${Math.round(value / 1_000_000)} млн`;
  if (abs >= 1_000) return `${Math.round(value / 1_000)} тыс`;
  return String(value);
}

interface TooltipPayloadItem {
  dataKey?: string | number;
  value?: number | string | null;
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayloadItem[]; label?: string | number }) {
  if (!active || !payload?.length) return null;
  const revenue = payload.find((p) => p.dataKey === 'revenue')?.value;
  const profit = payload.find((p) => p.dataKey === 'profit')?.value;
  return (
    <div className="rounded-lg border border-border bg-surface px-2.5 py-2 text-[11px] shadow-lg">
      <div className="mb-1 font-semibold text-ink">{label} год</div>
      <div className="flex items-center gap-1.5 text-ink-soft">
        <span className="h-2 w-2 rounded-sm bg-accent" />
        Выручка <b className="text-ink">{formatMoney(typeof revenue === 'number' ? revenue : null)}</b>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-ink-soft">
        <span className="h-0.5 w-3 bg-success" />
        Прибыль <b className="text-ink">{formatMoney(typeof profit === 'number' ? profit : null)}</b>
      </div>
    </div>
  );
}

export function FinanceTrend({ years }: { years: GlobalSupplierFinanceYear[] }) {
  const data = years.filter((y) => y.revenue != null || y.profit != null);
  if (data.length < 2) return null; // one point isn't a trend

  const first = data[0];
  const last = data[data.length - 1];
  const revenueGrew = (last.revenue ?? 0) >= (first.revenue ?? 0);
  const profitFell = (last.profit ?? 0) < (first.profit ?? 0);
  const hasLoss = data.some((y) => (y.profit ?? 0) < 0);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Динамика</h3>
        <span className="text-[10.5px] text-ink-faint">
          {first.report_year}–{last.report_year}
        </span>
      </div>

      <div className="mt-2 h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <CartesianGrid stroke="var(--color-border)" vertical={false} />
            <XAxis dataKey="report_year" tickLine={false} axisLine={{ stroke: 'var(--color-border-strong)' }} tick={{ fontSize: 10, fill: 'var(--color-ink-faint)' }} />
            <YAxis yAxisId="revenue" tickFormatter={axisTick} tickLine={false} axisLine={false} width={44} tick={{ fontSize: 10, fill: 'var(--color-ink-faint)' }} />
            <YAxis yAxisId="profit" orientation="right" tickFormatter={axisTick} tickLine={false} axisLine={false} width={44} tick={{ fontSize: 10, fill: 'var(--color-ink-faint)' }} />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--color-surface-hover)' }} />
            <Bar yAxisId="revenue" dataKey="revenue" name="Выручка" fill="var(--color-accent-border)" radius={[3, 3, 0, 0]} maxBarSize={34} />
            <Line
              yAxisId="profit"
              type="monotone"
              dataKey="profit"
              name="Прибыль"
              stroke={profitFell ? 'var(--color-danger)' : 'var(--color-success)'}
              strokeWidth={2}
              dot={{ r: 2.5, strokeWidth: 0, fill: profitFell ? 'var(--color-danger)' : 'var(--color-success)' }}
              activeDot={{ r: 4 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center justify-between text-[10.5px] text-ink-faint">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-2 rounded-sm bg-accent-border" />
          Выручка
        </span>
        <span className="inline-flex items-center gap-1">
          <span className={`h-0.5 w-3 ${profitFell ? 'bg-danger' : 'bg-success'}`} />
          Прибыль
        </span>
      </div>

      {hasLoss && <p className="mt-2 text-[11px] text-danger">Были убыточные годы — проверьте условия предоплаты.</p>}
      {!hasLoss && revenueGrew && profitFell && (
        <p className="mt-2 text-[11px] text-warning">Выручка растёт, а прибыль снижается — стоит уточнить условия оплаты.</p>
      )}
      {!hasLoss && !revenueGrew && <p className="mt-2 text-[11px] text-warning">Выручка снижается — учитывайте при крупном или длительном заказе.</p>}
    </div>
  );
}
