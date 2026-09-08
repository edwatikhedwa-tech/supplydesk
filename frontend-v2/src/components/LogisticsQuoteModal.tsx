import { AlertTriangle, Truck } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { LogisticsQuote } from '../lib/types';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

const STATUS_LABEL: Record<string, string> = {
  unavailable: 'Расчёт доставки временно недоступен.',
  invalid_input: 'Перевозчик не принял эти параметры груза или маршрута.',
  rate_limited: 'Слишком много запросов к перевозчику — попробуйте через минуту.',
  provider_error: 'Перевозчик не ответил. Попробуйте ещё раз позже.',
};

interface FieldState {
  routeFrom: string;
  routeTo: string;
  places: string;
  weightKg: string;
  volumeM3: string;
  lengthCm: string;
  widthCm: string;
  heightCm: string;
}

const emptyFields: FieldState = {
  routeFrom: '',
  routeTo: '',
  places: '1',
  weightKg: '',
  volumeM3: '',
  lengthCm: '',
  widthCm: '',
  heightCm: '',
};

export function LogisticsQuoteModal({
  requestId,
  supplierId,
  supplierName,
  onClose,
}: {
  requestId: number;
  supplierId: number;
  supplierName: string;
  onClose: () => void;
}) {
  const [fields, setFields] = useState<FieldState>(emptyFields);
  const [loadingExisting, setLoadingExisting] = useState(true);
  const [quote, setQuote] = useState<LogisticsQuote | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .getLogisticsQuote(requestId, supplierId)
      .then((res) => {
        if (res.quote) {
          setQuote(res.quote);
          setFields({
            routeFrom: res.quote.route_from,
            routeTo: res.quote.route_to,
            places: String(res.quote.cargo_places),
            weightKg: String(res.quote.cargo_weight_kg),
            volumeM3: String(res.quote.cargo_volume_m3),
            lengthCm: '',
            widthCm: '',
            heightCm: '',
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoadingExisting(false));
  }, [requestId, supplierId]);

  function set<K extends keyof FieldState>(key: K, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  const numbers = {
    places: Number(fields.places),
    weightKg: Number(fields.weightKg),
    volumeM3: Number(fields.volumeM3),
    lengthCm: Number(fields.lengthCm),
    widthCm: Number(fields.widthCm),
    heightCm: Number(fields.heightCm),
  };
  const isValid =
    fields.routeFrom.trim() !== '' &&
    fields.routeTo.trim() !== '' &&
    Object.values(numbers).every((n) => Number.isFinite(n) && n > 0);

  async function handleCalculate() {
    if (!isValid) {
      setError('Заполните все поля — маршрут, число мест, вес, объём и габариты одного места.');
      return;
    }
    setError('');
    setCalculating(true);
    try {
      const res = await api.calculateLogisticsQuote(requestId, supplierId, {
        route_from: fields.routeFrom.trim(),
        route_to: fields.routeTo.trim(),
        cargo: {
          places: numbers.places,
          weight_kg: numbers.weightKg,
          volume_m3: numbers.volumeM3,
          max_length_cm: numbers.lengthCm,
          max_width_cm: numbers.widthCm,
          max_height_cm: numbers.heightCm,
        },
      });
      setQuote(res.quote);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось связаться с бэкендом.');
    } finally {
      setCalculating(false);
    }
  }

  return (
    <Modal title={`Стоимость доставки — ${supplierName}`} onClose={onClose} width={480}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[12px] font-medium text-ink-soft">Откуда</label>
            <input
              value={fields.routeFrom}
              onChange={(e) => set('routeFrom', e.target.value)}
              placeholder="Москва"
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12px] font-medium text-ink-soft">Куда</label>
            <input
              value={fields.routeTo}
              onChange={(e) => set('routeTo', e.target.value)}
              placeholder="Краснодар"
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-[12px] font-medium text-ink-soft">Мест</label>
            <input
              type="number"
              min={1}
              value={fields.places}
              onChange={(e) => set('places', e.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12px] font-medium text-ink-soft">Вес, кг</label>
            <input
              type="number"
              min={0}
              value={fields.weightKg}
              onChange={(e) => set('weightKg', e.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12px] font-medium text-ink-soft">Объём, м³</label>
            <input
              type="number"
              min={0}
              step="0.01"
              value={fields.volumeM3}
              onChange={(e) => set('volumeM3', e.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-[12px] font-medium text-ink-soft">Габариты одного места, см (Д × Ш × В)</label>
          <div className="grid grid-cols-3 gap-3">
            <input
              type="number"
              min={0}
              placeholder="Д"
              value={fields.lengthCm}
              onChange={(e) => set('lengthCm', e.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
            <input
              type="number"
              min={0}
              placeholder="Ш"
              value={fields.widthCm}
              onChange={(e) => set('widthCm', e.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
            <input
              type="number"
              min={0}
              placeholder="В"
              value={fields.heightCm}
              onChange={(e) => set('heightCm', e.target.value)}
              className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
        </div>

        {error && (
          <p className="flex items-start gap-1.5 text-[12px] text-danger">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            {error}
          </p>
        )}

        {quote && !calculating && (
          <div className="rounded-md border border-border bg-surface-hover px-3.5 py-3">
            {quote.status === 'success' ? (
              <>
                <p className="text-[18px] font-semibold text-ink">
                  {quote.price?.toLocaleString('ru-RU')} {quote.currency === 'RUB' ? '₽' : quote.currency}
                </p>
                <p className="mt-0.5 text-[12px] text-ink-muted">
                  {quote.carrier === 'dellin' ? 'Деловые Линии' : quote.carrier}
                  {quote.term_days ? ` · ${quote.term_days} дн. в пути` : ''}
                </p>
              </>
            ) : (
              <p className="flex items-start gap-1.5 text-[12.5px] text-warning">
                <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                {STATUS_LABEL[quote.status] ?? 'Не удалось получить стоимость.'}
              </p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={onClose}>
            Закрыть
          </Button>
          <Button variant="primary" icon={<Truck size={13} />} disabled={calculating || loadingExisting} onClick={() => void handleCalculate()}>
            {calculating ? 'Считаем…' : 'Посчитать доставку'}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
