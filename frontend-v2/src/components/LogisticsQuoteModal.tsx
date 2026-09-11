import clsx from 'clsx';
import { AlertTriangle, Truck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { FreightTypeOption, LogisticsQuote, LogisticsRouteVariant, TerminalOption } from '../lib/types';
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
  routeFromVariant: LogisticsRouteVariant;
  routeFromTerminalId: number | null;
  routeTo: string;
  routeToVariant: LogisticsRouteVariant;
  routeToTerminalId: number | null;
  places: string;
  weightKg: string;
  volumeM3: string;
  lengthCm: string;
  widthCm: string;
  heightCm: string;
}

const emptyFields: FieldState = {
  routeFrom: '',
  routeFromVariant: 'address',
  routeFromTerminalId: null,
  routeTo: '',
  routeToVariant: 'address',
  routeToTerminalId: null,
  places: '1',
  weightKg: '',
  volumeM3: '',
  lengthCm: '',
  widthCm: '',
  heightCm: '',
};

/**
 * Поиск-по-мере-набора с задержкой. `search` держится в ref, а не в массиве
 * зависимостей эффекта: у вызывающих это обычно новая функция на каждый
 * рендер (замыкание на direction/вариант конкретного поля), и включение её в
 * зависимости запускало бы поиск заново при каждом ре-рендере, а не только
 * при изменении текста.
 */
function useAutocomplete<T>(
  query: string,
  enabled: boolean,
  search: (q: string) => Promise<{ status: string; items: T[] }>,
): { options: T[]; loading: boolean } {
  const [options, setOptions] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  const searchRef = useRef(search);
  searchRef.current = search;

  useEffect(() => {
    const trimmed = query.trim();
    if (!enabled || trimmed.length < 2) {
      setOptions([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      searchRef
        .current(trimmed)
        .then((res) => {
          if (!cancelled) setOptions(res.status === 'success' ? res.items : []);
        })
        .catch(() => {
          if (!cancelled) setOptions([]);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, enabled]);

  return { options, loading };
}

/** Текстовое поле с выпадающим списком вариантов — общий UI для "Характер
 * груза" и выбора терминала (Пункт приёма/выдачи). Значение считается
 * "выбранным из списка", пока не начали печатать заново после выбора. */
function AutocompleteField<T>({
  value,
  onChange,
  onSelect,
  options,
  loading,
  hasSelection,
  getKey,
  renderOption,
  placeholder,
}: {
  value: string;
  onChange: (text: string) => void;
  onSelect: (option: T) => void;
  options: T[];
  loading: boolean;
  hasSelection: boolean;
  getKey: (option: T) => string;
  renderOption: (option: T) => React.ReactNode;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const blurTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleBlur() {
    // Небольшая задержка, чтобы клик по варианту в списке успел сработать
    // раньше, чем закроется сам список по потере фокуса.
    blurTimer.current = setTimeout(() => setOpen(false), 150);
  }

  function handleSelect(option: T) {
    if (blurTimer.current) clearTimeout(blurTimer.current);
    onSelect(option);
    setOpen(false);
  }

  const showDropdown = open && !hasSelection && (loading || options.length > 0);

  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={handleBlur}
        placeholder={placeholder}
        className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
      />
      {showDropdown && (
        <div className="absolute z-10 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-border-strong bg-surface shadow-md">
          {loading && <p className="px-3 py-2 text-[12px] text-ink-muted">Ищем…</p>}
          {!loading &&
            options.map((option) => (
              <button
                key={getKey(option)}
                type="button"
                onMouseDown={(e) => {
                  // preventDefault keeps focus deterministically on the text
                  // input instead of racing the button's own default
                  // mousedown-focus behaviour -- without it, a click right
                  // after selecting a suggestion could land on whichever
                  // element the browser left focused.
                  e.preventDefault();
                  handleSelect(option);
                }}
                className="block w-full px-3 py-1.5 text-left text-[12.5px] text-ink hover:bg-surface-hover"
              >
                {renderOption(option)}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}

function RouteVariantToggle({
  value,
  onChange,
  terminalLabel,
}: {
  value: LogisticsRouteVariant;
  onChange: (value: LogisticsRouteVariant) => void;
  terminalLabel: string;
}) {
  return (
    <div className="inline-flex rounded-md border border-border-strong bg-surface p-0.5 text-[11px]">
      {(['address', 'terminal'] as const).map((variant) => (
        <button
          key={variant}
          type="button"
          onClick={() => onChange(variant)}
          className={clsx(
            'rounded px-2 py-0.5 font-medium transition-colors',
            value === variant ? 'bg-ink text-white' : 'text-ink-muted hover:text-ink',
          )}
        >
          {variant === 'address' ? 'Адрес' : terminalLabel}
        </button>
      ))}
    </div>
  );
}

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

  // "Характер груза" — необязательное поле API (cargo.freightUID), но это не
  // свободный текст: значение должно быть UID из справочника Деловых Линий,
  // который ищется отдельным вызовом по мере набора. freightUid=null, пока
  // текст не совпадает с выбранным вариантом из списка — тогда поле просто не
  // отправляется, и калькулятор считает груз по умолчанию.
  const [freightQuery, setFreightQuery] = useState('');
  const [freightUid, setFreightUid] = useState<string | null>(null);
  const freightSearch = useAutocomplete<FreightTypeOption>(freightQuery, !freightUid, api.searchFreightTypes);

  // "Пункт приёма/выдачи" — API отклоняет произвольный текст адреса для
  // variant="terminal" (ошибка 180002 "Указан некорректный адрес: требуется
  // указать терминал", подтверждено живым вызовом 2026-09-11): нужен
  // конкретный terminal_id, выбранный из списка терминалов введённого города.
  const terminalFromSearch = useAutocomplete<TerminalOption>(
    fields.routeFrom,
    fields.routeFromVariant === 'terminal' && fields.routeFromTerminalId === null,
    (q) => api.searchTerminals(q, 'derival'),
  );
  const terminalToSearch = useAutocomplete<TerminalOption>(
    fields.routeTo,
    fields.routeToVariant === 'terminal' && fields.routeToTerminalId === null,
    (q) => api.searchTerminals(q, 'arrival'),
  );

  useEffect(() => {
    api
      .getLogisticsQuote(requestId, supplierId)
      .then((res) => {
        if (res.quote) {
          setQuote(res.quote);
          setFields((prev) => ({
            ...prev,
            routeFrom: res.quote!.route_from,
            routeTo: res.quote!.route_to,
            places: String(res.quote!.cargo_places),
            weightKg: String(res.quote!.cargo_weight_kg),
            volumeM3: String(res.quote!.cargo_volume_m3),
          }));
        }
      })
      .catch(() => {})
      .finally(() => setLoadingExisting(false));
  }, [requestId, supplierId]);

  function set<K extends keyof FieldState>(key: K, value: FieldState[K]) {
    setFields((prev) => ({ ...prev, [key]: value }));
  }

  function setRouteFromVariant(variant: LogisticsRouteVariant) {
    setFields((prev) => ({ ...prev, routeFromVariant: variant, routeFromTerminalId: null }));
  }

  function setRouteToVariant(variant: LogisticsRouteVariant) {
    setFields((prev) => ({ ...prev, routeToVariant: variant, routeToTerminalId: null }));
  }

  function onFreightInputChange(value: string) {
    setFreightQuery(value);
    setFreightUid(null);
  }

  function selectFreightOption(option: FreightTypeOption) {
    setFreightQuery(option.value);
    setFreightUid(option.uid);
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
    (fields.routeFromVariant === 'address' || fields.routeFromTerminalId !== null) &&
    (fields.routeToVariant === 'address' || fields.routeToTerminalId !== null) &&
    Object.values(numbers).every((n) => Number.isFinite(n) && n > 0);

  async function handleCalculate() {
    if (!isValid) {
      setError(
        fields.routeFromTerminalId === null && fields.routeFromVariant === 'terminal'
          ? 'Выберите пункт приёма из списка терминалов.'
          : fields.routeToTerminalId === null && fields.routeToVariant === 'terminal'
            ? 'Выберите пункт выдачи из списка терминалов.'
            : 'Заполните все поля — маршрут, число мест, вес, объём и габариты одного места.',
      );
      return;
    }
    setError('');
    setCalculating(true);
    try {
      const res = await api.calculateLogisticsQuote(requestId, supplierId, {
        route_from: fields.routeFrom.trim(),
        route_to: fields.routeTo.trim(),
        route_from_variant: fields.routeFromVariant,
        route_to_variant: fields.routeToVariant,
        route_from_terminal_id: fields.routeFromTerminalId,
        route_to_terminal_id: fields.routeToTerminalId,
        cargo: {
          places: numbers.places,
          weight_kg: numbers.weightKg,
          volume_m3: numbers.volumeM3,
          max_length_cm: numbers.lengthCm,
          max_width_cm: numbers.widthCm,
          max_height_cm: numbers.heightCm,
          freight_uid: freightUid,
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
            <div className="mb-1 flex items-center justify-between">
              <label className="block text-[12px] font-medium text-ink-soft">Откуда</label>
              <RouteVariantToggle value={fields.routeFromVariant} onChange={setRouteFromVariant} terminalLabel="Пункт приёма" />
            </div>
            {fields.routeFromVariant === 'address' ? (
              <input
                value={fields.routeFrom}
                onChange={(e) => set('routeFrom', e.target.value)}
                placeholder="Москва"
                className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
              />
            ) : (
              <AutocompleteField
                value={fields.routeFrom}
                onChange={(text) => setFields((prev) => ({ ...prev, routeFrom: text, routeFromTerminalId: null }))}
                onSelect={(option: TerminalOption) =>
                  setFields((prev) => ({ ...prev, routeFrom: `${option.name} (${option.address})`, routeFromTerminalId: option.id }))
                }
                options={terminalFromSearch.options}
                loading={terminalFromSearch.loading}
                hasSelection={fields.routeFromTerminalId !== null}
                getKey={(option) => String(option.id)}
                renderOption={(option) => (
                  <>
                    <span className="block font-medium">{option.name}</span>
                    <span className="block text-[11px] text-ink-muted">{option.address}</span>
                  </>
                )}
                placeholder="Город, например: Москва"
              />
            )}
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="block text-[12px] font-medium text-ink-soft">Куда</label>
              <RouteVariantToggle value={fields.routeToVariant} onChange={setRouteToVariant} terminalLabel="Пункт выдачи" />
            </div>
            {fields.routeToVariant === 'address' ? (
              <input
                value={fields.routeTo}
                onChange={(e) => set('routeTo', e.target.value)}
                placeholder="Краснодар"
                className="h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
              />
            ) : (
              <AutocompleteField
                value={fields.routeTo}
                onChange={(text) => setFields((prev) => ({ ...prev, routeTo: text, routeToTerminalId: null }))}
                onSelect={(option: TerminalOption) =>
                  setFields((prev) => ({ ...prev, routeTo: `${option.name} (${option.address})`, routeToTerminalId: option.id }))
                }
                options={terminalToSearch.options}
                loading={terminalToSearch.loading}
                hasSelection={fields.routeToTerminalId !== null}
                getKey={(option) => String(option.id)}
                renderOption={(option) => (
                  <>
                    <span className="block font-medium">{option.name}</span>
                    <span className="block text-[11px] text-ink-muted">{option.address}</span>
                  </>
                )}
                placeholder="Город, например: Краснодар"
              />
            )}
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

        <div>
          <label className="mb-1 block text-[12px] font-medium text-ink-soft">Характер груза (необязательно)</label>
          <AutocompleteField
            value={freightQuery}
            onChange={onFreightInputChange}
            onSelect={selectFreightOption}
            options={freightSearch.options}
            loading={freightSearch.loading}
            hasSelection={freightUid !== null}
            getKey={(option) => option.uid}
            renderOption={(option) => option.value}
            placeholder="Например: автозапчасти, коробка передач"
          />
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
