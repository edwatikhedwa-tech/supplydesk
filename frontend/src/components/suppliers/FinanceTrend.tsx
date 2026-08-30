import {
  Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { FinanceYear } from '@/lib/types';
import { formatRubCompact } from './RegistryFinanceRow';

/** Динамика выручки и прибыли по годам.
 *
 *  Зачем график, а не таблица чисел: закупщику важен не оборот сам по себе,
 *  а его направление. «Выручка растёт, прибыль падает» — повод задать вопрос
 *  об условиях оплаты; «выручка падает третий год» — повод не сажать на этого
 *  поставщика критичную позицию. Число такого не показывает, форма — показывает.
 *
 *  Почему Recharts, а не самодельный SVG: предыдущая версия рисовалась вручную
 *  и потому не имела ни осей, ни подписей значений, ни общей шкалы — прибыль
 *  накладывалась отдельной линией в собственном масштабе, из-за чего её
 *  положение относительно столбцов ничего не значило. Прочитать по такому
 *  графику можно было только «растёт/падает», а величину — нет.
 *
 *  Форма: столбцы для выручки (сравнение величин одного ряда во времени) и
 *  линия для прибыли на второй оси — прибыль на один-два порядка меньше
 *  выручки, в общей шкале она легла бы в ноль.
 */

const RUB = (value: number | null | undefined) => (value == null ? '—' : formatRubCompact(value));

/** Подписи оси: короткие, иначе они съедают ширину карточки. */
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

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  const revenue = payload.find((p) => p.dataKey === 'revenue')?.value;
  const profit = payload.find((p) => p.dataKey === 'profit')?.value;
  return (
    <div className="rounded-lg border border-ink-200 bg-white px-2.5 py-2 text-2xs shadow-panel">
      <div className="mb-1 font-semibold text-ink-800">{label} год</div>
      <div className="flex items-center gap-1.5 text-ink-600">
        <span className="h-2 w-2 rounded-sm bg-accent-400" />
        Выручка <b className="text-ink-800">{RUB(typeof revenue === 'number' ? revenue : null)}</b>
      </div>
      <div className="mt-0.5 flex items-center gap-1.5 text-ink-600">
        <span className="h-0.5 w-3 bg-emerald-500" />
        Прибыль <b className="text-ink-800">{RUB(typeof profit === 'number' ? profit : null)}</b>
      </div>
    </div>
  );
}

export function FinanceTrend({ years }: { years: FinanceYear[] }) {
  const data = years.filter((y) => y.revenue != null || y.profit != null);
  if (data.length < 2) return null; // одна точка — это не динамика

  const first = data[0];
  const last = data[data.length - 1];
  const revenueGrew = (last.revenue ?? 0) >= (first.revenue ?? 0);
  const profitFell = (last.profit ?? 0) < (first.profit ?? 0);
  const hasLoss = data.some((y) => (y.profit ?? 0) < 0);

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <b className="text-xs uppercase tracking-wider text-ink-500">Динамика</b>
        <span className="text-2xs text-ink-400">{first.report_year}–{last.report_year}</span>
      </div>

      <div className="mt-2 h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <CartesianGrid stroke="#eef1f5" vertical={false} />
            <XAxis
              dataKey="report_year"
              tickLine={false}
              axisLine={{ stroke: '#e3e8ef' }}
              tick={{ fontSize: 10, fill: '#8a94a6' }}
            />
            <YAxis
              yAxisId="revenue"
              tickFormatter={axisTick}
              tickLine={false}
              axisLine={false}
              width={44}
              tick={{ fontSize: 10, fill: '#8a94a6' }}
            />
            <YAxis
              yAxisId="profit"
              orientation="right"
              tickFormatter={axisTick}
              tickLine={false}
              axisLine={false}
              width={44}
              tick={{ fontSize: 10, fill: '#8a94a6' }}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(15,23,42,0.04)' }} />
            <Bar yAxisId="revenue" dataKey="revenue" name="Выручка" fill="#93b4fc" radius={[3, 3, 0, 0]} maxBarSize={34} />
            <Line
              yAxisId="profit"
              type="monotone"
              dataKey="profit"
              name="Прибыль"
              stroke={profitFell ? '#f43f5e' : '#10b981'}
              strokeWidth={2}
              dot={{ r: 2.5, strokeWidth: 0, fill: profitFell ? '#f43f5e' : '#10b981' }}
              activeDot={{ r: 4 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center justify-between text-2xs text-ink-400">
        <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-[#93b4fc]" />Выручка</span>
        <span className="inline-flex items-center gap-1">
          <span className={`h-0.5 w-3 ${profitFell ? 'bg-rose-500' : 'bg-emerald-500'}`} />Прибыль
        </span>
      </div>

      {/* Вывод словами: смысл графика не должен зависеть от того, умеет ли
          читатель считывать формы. Названы только случаи, которые
          действительно меняют решение закупщика. */}
      {hasLoss && (
        <p className="mt-2 text-2xs text-rose-700">Были убыточные годы — проверьте условия предоплаты.</p>
      )}
      {!hasLoss && revenueGrew && profitFell && (
        <p className="mt-2 text-2xs text-amber-700">Выручка растёт, а прибыль снижается — стоит уточнить условия оплаты.</p>
      )}
      {!hasLoss && !revenueGrew && (
        <p className="mt-2 text-2xs text-amber-700">Выручка снижается — учитывайте при крупном или длительном заказе.</p>
      )}
    </div>
  );
}
