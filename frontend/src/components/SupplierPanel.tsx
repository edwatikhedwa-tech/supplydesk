import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Ban, X, Mail, Phone, Building2, ChevronRight, Globe, Send, ShieldOff, ExternalLink, Loader2 } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import type { LogisticsQuote, Supplier } from '@/lib/types';
import { MailStatusBadges } from '@/components/MailStatusBadges';
import { DELIVERY_META } from '@/useRequestState';
import { displaySupplierName } from '@/lib/utils';
import { RegistryFinanceRow } from '@/components/suppliers/RegistryFinanceRow';
import { CopyButton } from '@/components/CopyButton';

interface Props {
  supplier: Supplier | null;
  requestId: number;
  itemNames: (supplier: Supplier) => string[];
  onClose: () => void;
  onWrite: (id: number) => void;
  onMarkIrrelevant: (id: number) => void;
  onSupplierUpdated: () => Promise<void> | void;
}

export function SupplierPanel({ supplier, requestId, itemNames, onClose, onWrite, onMarkIrrelevant, onSupplierUpdated }: Props) {
  const [innInput, setInnInput] = useState('');
  const [savingInn, setSavingInn] = useState(false);
  const [innMessage, setInnMessage] = useState('');
  const [innError, setInnError] = useState('');
  const [blacklistOpen, setBlacklistOpen] = useState(false);
  const [blacklistReason, setBlacklistReason] = useState('');
  const [blacklisting, setBlacklisting] = useState(false);
  const [blacklistError, setBlacklistError] = useState('');

  const [routeFrom, setRouteFrom] = useState('');
  const [routeTo, setRouteTo] = useState('');
  const [cargoPlaces, setCargoPlaces] = useState('');
  const [cargoWeightKg, setCargoWeightKg] = useState('');
  const [cargoVolumeM3, setCargoVolumeM3] = useState('');
  const [cargoMaxLength, setCargoMaxLength] = useState('');
  const [cargoMaxWidth, setCargoMaxWidth] = useState('');
  const [cargoMaxHeight, setCargoMaxHeight] = useState('');
  const [calculatingLogistics, setCalculatingLogistics] = useState(false);
  const [logisticsError, setLogisticsError] = useState('');
  const [logisticsQuote, setLogisticsQuote] = useState<LogisticsQuote | null>(null);
  const [logisticsMessage, setLogisticsMessage] = useState('');

  useEffect(() => {
    if (!supplier) return;
    setInnInput(supplier.inn || '');
    setInnMessage('');
    setInnError('');
    setBlacklistOpen(false);
    setBlacklistReason('');
    setBlacklistError('');
    setRouteFrom('');
    setRouteTo('');
    setCargoPlaces('');
    setCargoWeightKg('');
    setCargoVolumeM3('');
    setCargoMaxLength('');
    setCargoMaxWidth('');
    setCargoMaxHeight('');
    setLogisticsError('');
    setLogisticsMessage('');
    setLogisticsQuote(null);
    let cancelled = false;
    void api.getLogisticsQuote(requestId, supplier.id).then((result) => {
      if (!cancelled) setLogisticsQuote(result.quote);
    }).catch(() => undefined);
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => { cancelled = true; window.removeEventListener('keydown', handleKey); };
  }, [supplier?.id, requestId, onClose]);

  if (!supplier) return null;
  const contactEmails = supplier.contact_emails?.length ? supplier.contact_emails : (supplier.email ? [supplier.email] : []);
  const contactSites = supplier.contact_sites?.length ? supplier.contact_sites : (supplier.host ? [supplier.host] : []);
  // A stray "…" mid-sentence in a SERP snippet reads as broken text — trim to
  // the last full sentence/clause instead of showing the raw cut.
  const cleanReason = supplier.reason?.replace(/\s*\.{2,}\s*$/, '').trim();

  const saveInn = async () => {
    setInnError('');
    setInnMessage('');
    const digits = innInput.replace(/\D/g, '');
    if (digits.length !== 10 && digits.length !== 12) {
      setInnError('Введите 10 или 12 цифр ИНН.');
      return;
    }
    setSavingInn(true);
    try {
      const result = await api.updateSupplierInn(requestId, supplier.id, digits);
      setInnInput(result.inn);
      setInnMessage(
        result.checko_status === 'loaded'
          ? 'ИНН сохранён, данные Checko обновлены.'
          : result.checko_status === 'not_found'
            ? 'ИНН сохранён, но компания не найдена в Checko.'
            : 'ИНН сохранён. Checko пока недоступен — обновление можно повторить позже.',
      );
      await onSupplierUpdated();
    } catch (error) {
      setInnError(error instanceof ApiError ? error.message : 'Не удалось сохранить ИНН.');
    } finally {
      setSavingInn(false);
    }
  };

  const logisticsGateReady = Boolean(
    routeFrom.trim() && routeTo.trim() &&
    Number(cargoPlaces) > 0 && Number(cargoWeightKg) > 0 && Number(cargoVolumeM3) > 0 &&
    Number(cargoMaxLength) > 0 && Number(cargoMaxWidth) > 0 && Number(cargoMaxHeight) > 0,
  );

  const logisticsStatusFallback: Record<string, string> = {
    unavailable: 'Не удалось получить тариф у перевозчика.',
    invalid_input: 'Деловые Линии отклонили запрос — проверьте маршрут и параметры груза.',
    rate_limited: 'Превышен лимит запросов к Деловым Линиям, попробуйте позже.',
    provider_error: 'Деловые Линии временно недоступны, попробуйте позже.',
  };

  const calculateLogistics = async () => {
    if (!logisticsGateReady) return;
    setLogisticsError('');
    setLogisticsMessage('');
    setCalculatingLogistics(true);
    try {
      const result = await api.calculateLogistics(requestId, supplier.id, {
        route_from: routeFrom.trim(),
        route_to: routeTo.trim(),
        cargo: {
          places: Number(cargoPlaces),
          weight_kg: Number(cargoWeightKg),
          volume_m3: Number(cargoVolumeM3),
          max_length_cm: Number(cargoMaxLength),
          max_width_cm: Number(cargoMaxWidth),
          max_height_cm: Number(cargoMaxHeight),
        },
      });
      setLogisticsQuote(result.quote);
      setLogisticsMessage(result.message || (result.quote.status !== 'success' ? logisticsStatusFallback[result.quote.status] || '' : ''));
    } catch (error) {
      setLogisticsError(error instanceof ApiError ? error.message : 'Не удалось рассчитать доставку.');
    } finally {
      setCalculatingLogistics(false);
    }
  };

  const addToBlacklist = async () => {
    const reason = blacklistReason.trim();
    if (!reason) {
      setBlacklistError('Укажите причину, чтобы запись можно было понять позже.');
      return;
    }
    setBlacklistError('');
    setBlacklisting(true);
    try {
      await api.addBlacklist({
        external_key: supplier.external_key,
        company_name: displaySupplierName(supplier.name, supplier.inn) || supplier.host,
        reason,
        supplier_id: supplier.id,
      });
      await onSupplierUpdated();
      onClose();
    } catch (error) {
      setBlacklistError(error instanceof ApiError ? error.message : 'Не удалось добавить компанию в ЧС.');
    } finally {
      setBlacklisting(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-ink-900/30" onClick={onClose} />
      <aside className="fixed right-0 top-0 bottom-0 z-50 flex w-full max-w-full flex-col overflow-y-auto bg-white shadow-panel sm:w-[440px]">
        {/* Шапка и блок реквизитов повторяют карточку на экране «Поставщики»
            (components/suppliers/SupplierPanel.tsx): одна и та же компания не
            должна выглядеть по-разному в зависимости от того, с какого экрана
            её открыли. */}
        <div className="flex items-start justify-between border-b border-ink-200 px-4 py-5 sm:px-6">
          <div className="min-w-0">
            <h2 title={supplier.name} className="break-words text-lg font-bold leading-tight text-ink-900 [overflow-wrap:anywhere]">{displaySupplierName(supplier.name, supplier.inn)}</h2>
            <div className="mt-1 break-words text-xs text-ink-500 [overflow-wrap:anywhere]">{supplier.inn ? `ИНН ${supplier.inn}` : supplier.host}</div>
            {supplier.inn_source === 'manual' && (
              <span className="mt-2 inline-flex items-center gap-1 rounded-full bg-accent-50 px-2 py-1 text-2xs font-semibold text-accent-700 ring-1 ring-accent-200">
                <AlertTriangle className="h-3 w-3" />Внесён пользователем
              </span>
            )}
            <div className="mt-2"><MailStatusBadges supplier={supplier} /></div>
          </div>
          <button onClick={onClose} aria-label="Закрыть карточку поставщика" className="shrink-0 rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-800"><X className="h-5 w-5" /></button>
        </div>

        <RegistryFinanceRow registry={supplier.registry} finances={supplier.finances} risks={supplier.risks} className="border-b border-ink-100 px-4 py-3 sm:px-6" />

        <section className="border-b border-ink-100 px-4 py-4 sm:px-6" aria-labelledby="manual-inn-label">
          <div className="flex items-center justify-between gap-3">
            <label id="manual-inn-label" htmlFor="supplier-inn" className="text-xs font-semibold uppercase tracking-wider text-ink-500">ИНН компании</label>
            {supplier.inn_source === 'manual' && <span className="text-2xs font-medium text-ink-500">Источник: пользователь</span>}
          </div>
          <div className="mt-2 flex min-w-0 gap-2">
            <input
              id="supplier-inn"
              value={innInput}
              onChange={(event) => setInnInput(event.target.value.replace(/\D/g, '').slice(0, 12))}
              inputMode="numeric"
              maxLength={12}
              placeholder="10 или 12 цифр"
              aria-describedby="supplier-inn-help"
              className="min-w-0 flex-1 rounded-lg border border-ink-200 px-3 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
            <button
              type="button"
              onClick={() => void saveInn()}
              disabled={savingInn}
              className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-accent-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-accent-700 disabled:opacity-60"
            >
              {savingInn && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {savingInn ? 'Проверяем' : 'Сохранить'}
            </button>
          </div>
          <p id="supplier-inn-help" className="mt-1.5 text-2xs leading-relaxed text-ink-500">После сохранения система запросит реквизиты и статус в Checko.</p>
          {innMessage && <p role="status" className="mt-2 break-words text-xs font-medium text-emerald-700">{innMessage}</p>}
          {innError && <p role="alert" className="mt-2 break-words text-xs font-medium text-rose-600">{innError}</p>}
        </section>

        <section className="border-b border-ink-100 px-4 py-4 sm:px-6" aria-labelledby="logistics-label">
          <label id="logistics-label" className="text-xs font-semibold uppercase tracking-wider text-ink-500">Логистика</label>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <input
              value={routeFrom}
              onChange={(event) => setRouteFrom(event.target.value)}
              placeholder="Город/терминал отправления"
              aria-label="Город или терминал отправления"
              className="min-w-0 rounded-lg border border-ink-200 px-3 py-2 text-sm text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
            <input
              value={routeTo}
              onChange={(event) => setRouteTo(event.target.value)}
              placeholder="Город/терминал назначения"
              aria-label="Город или терминал назначения"
              className="min-w-0 rounded-lg border border-ink-200 px-3 py-2 text-sm text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
            <input
              value={cargoPlaces}
              onChange={(event) => setCargoPlaces(event.target.value.replace(/[^\d]/g, ''))}
              inputMode="numeric"
              placeholder="Мест, шт"
              aria-label="Число грузовых мест"
              className="min-w-0 rounded-lg border border-ink-200 px-3 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
            <input
              value={cargoWeightKg}
              onChange={(event) => setCargoWeightKg(event.target.value.replace(/[^\d.,]/g, ''))}
              inputMode="decimal"
              placeholder="Общий вес, кг"
              aria-label="Общий вес груза в килограммах"
              className="min-w-0 rounded-lg border border-ink-200 px-3 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
            <input
              value={cargoVolumeM3}
              onChange={(event) => setCargoVolumeM3(event.target.value.replace(/[^\d.,]/g, ''))}
              inputMode="decimal"
              placeholder="Общий объём, м³"
              aria-label="Общий объём груза в кубических метрах"
              className="min-w-0 rounded-lg border border-ink-200 px-3 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
            />
            <div className="grid grid-cols-3 gap-1">
              <input
                value={cargoMaxLength}
                onChange={(event) => setCargoMaxLength(event.target.value.replace(/[^\d.,]/g, ''))}
                inputMode="decimal"
                placeholder="Д, см"
                aria-label="Максимальная длина одного места в сантиметрах"
                className="min-w-0 rounded-lg border border-ink-200 px-2 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
              />
              <input
                value={cargoMaxWidth}
                onChange={(event) => setCargoMaxWidth(event.target.value.replace(/[^\d.,]/g, ''))}
                inputMode="decimal"
                placeholder="Ш, см"
                aria-label="Максимальная ширина одного места в сантиметрах"
                className="min-w-0 rounded-lg border border-ink-200 px-2 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
              />
              <input
                value={cargoMaxHeight}
                onChange={(event) => setCargoMaxHeight(event.target.value.replace(/[^\d.,]/g, ''))}
                inputMode="decimal"
                placeholder="В, см"
                aria-label="Максимальная высота одного места в сантиметрах"
                className="min-w-0 rounded-lg border border-ink-200 px-2 py-2 text-sm tabular-nums text-ink-800 outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-100"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={() => void calculateLogistics()}
            disabled={!logisticsGateReady || calculatingLogistics}
            className="mt-2 inline-flex w-full shrink-0 items-center justify-center gap-1.5 rounded-lg bg-accent-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-accent-700 disabled:opacity-60"
          >
            {calculatingLogistics && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {calculatingLogistics ? 'Считаем' : 'Рассчитать доставку'}
          </button>
          <p className="mt-1.5 text-2xs leading-relaxed text-ink-500">Расчёт выполняется по калькулятору Деловых Линий. Все поля маршрута и груза обязательны.</p>
          {logisticsQuote && logisticsQuote.status === 'success' && (
            <div role="status" className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              <p className="font-semibold">{logisticsQuote.carrier === 'dellin' ? 'Деловые Линии' : logisticsQuote.carrier}: {logisticsQuote.price?.toLocaleString('ru-RU')} {logisticsQuote.currency}</p>
              <p className="mt-0.5">{logisticsQuote.term_days != null ? `Срок: ${logisticsQuote.term_days} дн.` : 'Срок доставки не рассчитан.'}</p>
              <p className="mt-0.5 text-emerald-700">Рассчитано {new Date(logisticsQuote.calculated_at).toLocaleString('ru-RU')}</p>
            </div>
          )}
          {logisticsQuote && logisticsQuote.status !== 'success' && (
            <p role="status" className="mt-2 break-words text-xs font-medium text-rose-600">
              {logisticsMessage || logisticsStatusFallback[logisticsQuote.status] || 'Не удалось получить тариф.'}
            </p>
          )}
          {logisticsError && <p role="alert" className="mt-2 break-words text-xs font-medium text-rose-600">{logisticsError}</p>}
        </section>

        <div className="group/row space-y-3 px-4 py-5 text-sm text-ink-700 sm:px-6">
          <p className="flex min-w-0 items-start gap-2">
            <Mail className="h-4 w-4 shrink-0 text-ink-400" />
            <span className="min-w-0 flex-1 break-words [overflow-wrap:anywhere]">{supplier.email ?? 'Нет email'}</span>
            {supplier.email && <CopyButton value={supplier.email} label="Скопировать адрес" />}
          </p>
          <p className="flex min-w-0 items-start gap-2">
            <Phone className="h-4 w-4 shrink-0 text-ink-400" />
            <span className="min-w-0 flex-1 break-words [overflow-wrap:anywhere]">{supplier.phone || 'Нет телефона'}</span>
            {supplier.phone && <CopyButton value={supplier.phone} label="Скопировать телефон" />}
          </p>
          {supplier.inn && (
            <p className="flex min-w-0 items-start gap-2">
              <Building2 className="h-4 w-4 shrink-0 text-ink-400" />ИНН {supplier.inn}
              <CopyButton value={supplier.inn} label="Скопировать ИНН" />
              <Link to={`/suppliers?search=${supplier.inn}`} className="ml-auto inline-flex items-center gap-0.5 text-xs font-medium text-accent-600 hover:text-accent-700">
                Карточка компании<ChevronRight className="h-3 w-3" />
              </Link>
            </p>
          )}
          <p className="flex min-w-0 items-start gap-2">
            <Globe className="h-4 w-4 shrink-0 text-ink-400" />
            {supplier.host ? (
              <a href={`https://${supplier.host}`} target="_blank" rel="noreferrer" className="min-w-0 flex-1 break-all hover:text-accent-600 hover:underline">{supplier.host}</a>
            ) : <span className="min-w-0 flex-1 break-words text-ink-400">Сайт не найден</span>}
          </p>
          {(contactEmails.length > 1 || contactSites.length > 1) && (
            <section className="space-y-3 rounded-xl border border-ink-100 bg-ink-50/60 p-3" aria-labelledby="supplier-contacts-label">
              <b id="supplier-contacts-label" className="text-xs uppercase tracking-wider text-ink-500">Контакты компании</b>
              {contactEmails.length > 1 && (
                <div>
                  <div className="text-2xs font-semibold uppercase tracking-wider text-ink-400">Email</div>
                  <div className="mt-1 space-y-1">
                    {contactEmails.map((email) => {
                      const contact = supplier.contacts?.find((item) => item.email === email);
                      const contactLabel = contact?.response_status === 'answered'
                        ? 'Получен ответ'
                        : contact?.response_status === 'waiting'
                          ? 'Ждём ответа'
                          : contact?.delivery_status && contact.delivery_status !== 'mixed'
                            ? DELIVERY_META[contact.delivery_status].label
                            : null;
                      return <div key={email} className="flex min-w-0 items-start gap-1.5 text-xs text-ink-700">
                        <Mail className="mt-0.5 h-3 w-3 shrink-0 text-ink-400" />
                        <span className="min-w-0 flex-1 break-all">{email}</span>
                        {contactLabel && <span className="shrink-0 text-2xs text-ink-400">{contactLabel}</span>}
                        <CopyButton value={email} label="Скопировать адрес" />
                      </div>;
                    })}
                  </div>
                </div>
              )}
              {contactSites.length > 1 && (
                <div>
                  <div className="text-2xs font-semibold uppercase tracking-wider text-ink-400">Сайты</div>
                  <div className="mt-1 space-y-1">
                    {contactSites.map((host) => (
                      <a key={host} href={`https://${host}`} target="_blank" rel="noreferrer" className="flex min-w-0 items-start gap-1.5 break-all text-xs text-accent-600 hover:underline">
                        <Globe className="mt-0.5 h-3 w-3 shrink-0" />{host}
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}
          <div className="pt-1">
            <b className="text-xs uppercase tracking-wider text-ink-500">Позиции</b>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {itemNames(supplier).length > 0 ? itemNames(supplier).map((item) => (
                <span key={item} className="max-w-full break-words rounded-md bg-ink-100 px-2 py-1 text-xs text-ink-600">{item}</span>
              )) : <span className="text-xs text-ink-600">—</span>}
            </div>
          </div>
          {(cleanReason || supplier.found_url) && (
            <div>
              <b className="text-xs uppercase tracking-wider text-ink-500">Почему найден</b>
              {cleanReason && <p className="mt-1.5 whitespace-pre-wrap break-words text-xs leading-relaxed text-ink-500">{cleanReason}</p>}
              {/* Сниппет — это пересказ страницы, а не сама страница. Прямая
                  ссылка позволяет за один клик убедиться, что поставщик
                  действительно торгует нужной позицией, а не попал в выдачу
                  случайной статьёй. */}
              {supplier.found_url && (
                <a
                  href={supplier.found_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1.5 inline-flex max-w-full items-center gap-1.5 text-xs font-medium text-accent-600 hover:underline"
                >
                  <ExternalLink className="h-3 w-3 shrink-0" />
                  <span>Открыть найденную страницу</span>
                </a>
              )}
            </div>
          )}
        </div>

        <div className="mt-auto space-y-2 border-t border-ink-100 px-4 py-4 sm:px-6">
          <button
            disabled={!supplier.email}
            onClick={() => onWrite(supplier.id)}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-accent-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-700 disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />Написать
          </button>
          <button
            onClick={() => onMarkIrrelevant(supplier.id)}
            className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-ink-200 px-3 py-2 text-sm font-medium text-ink-600 transition-colors hover:border-rose-200 hover:text-rose-600"
          >
            <ShieldOff className="h-3.5 w-3.5" />Убрать из этой заявки
          </button>
          {blacklistOpen ? (
            <div className="space-y-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
              <label htmlFor="request-blacklist-reason" className="block text-xs font-semibold text-rose-700">Почему добавить в ЧС?</label>
              <textarea
                id="request-blacklist-reason"
                value={blacklistReason}
                onChange={(event) => setBlacklistReason(event.target.value.slice(0, 500))}
                rows={3}
                placeholder="Например: не поставляет нужную категорию"
                className="w-full resize-y rounded-lg border border-rose-200 bg-white px-2.5 py-2 text-sm text-ink-800 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
              />
              {blacklistError && <p role="alert" className="break-words text-xs font-medium text-rose-700">{blacklistError}</p>}
              <div className="flex gap-2">
                <button type="button" onClick={() => void addToBlacklist()} disabled={blacklisting} className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white hover:bg-rose-700 disabled:opacity-60">
                  {blacklisting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Добавить в ЧС
                </button>
                <button type="button" onClick={() => setBlacklistOpen(false)} disabled={blacklisting} className="rounded-lg border border-ink-200 px-3 py-2 text-xs font-semibold text-ink-600 hover:bg-white disabled:opacity-60">Отмена</button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => { setBlacklistError(''); setBlacklistOpen(true); }}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-rose-200 px-3 py-2 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50"
            >
              <Ban className="h-3.5 w-3.5" />В чёрный список
            </button>
          )}
        </div>
      </aside>
    </>
  );
}
