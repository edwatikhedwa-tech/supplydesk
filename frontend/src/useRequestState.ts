import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import type { RequestDetail, Supplier, SupplierDeliveryCounts, SupplierDeliveryStatus } from '@/lib/types';

export type FilterKey = 'all' | 'with_contacts' | 'without_contacts' | 'not_sent' | 'selected' | 'queued' | 'accepted' | 'waiting' | 'answered' | 'error' | 'bounce' | 'delivery_unknown';
export const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'with_contacts', label: 'С контактами' },
  { key: 'without_contacts', label: 'Без контакта' },
  { key: 'not_sent', label: 'Ещё не отправляли' },
  { key: 'selected', label: 'Выбранные' },
  { key: 'queued', label: 'Ожидает отправки' },
  { key: 'accepted', label: 'Отправлено' },
  { key: 'waiting', label: 'Ждём ответа' },
  { key: 'answered', label: 'Получен ответ' },
  { key: 'error', label: 'Ошибка отправки' },
  { key: 'bounce', label: 'Не доставлено' },
  { key: 'delivery_unknown', label: 'Статус неизвестен' },
];

export type SortKey = 'relevance' | 'name' | 'status';
export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'relevance', label: 'По релевантности' },
  { key: 'name', label: 'По названию' },
  { key: 'status', label: 'По статусу' },
];

const STATUS_ORDER: Record<SupplierDeliveryStatus, number> = { bounced: 0, failed: 1, delivery_unknown: 2, queued: 3, accepted: 4, cancelled: 5, not_sent: 6, mixed: 7 };

export const DELIVERY_META: Record<Exclude<SupplierDeliveryStatus, 'mixed'>, { label: string; icon: string; badge: string; title?: string }> = {
  not_sent: { label: 'Ещё не отправляли', icon: '○', badge: 'bg-ink-100 text-ink-600 ring-ink-200' },
  queued: { label: 'Ожидает отправки', icon: '◷', badge: 'bg-amber-50 text-amber-700 ring-amber-200' },
  accepted: { label: 'Отправлено', icon: '↗', badge: 'bg-accent-50 text-accent-700 ring-accent-200', title: 'Почтовый сервер принял письмо. Доставка во входящие не гарантируется.' },
  failed: { label: 'Ошибка отправки', icon: '!', badge: 'bg-rose-50 text-rose-700 ring-rose-200' },
  delivery_unknown: { label: 'Статус неизвестен', icon: '?', badge: 'bg-orange-50 text-orange-800 ring-orange-200' },
  bounced: { label: 'Не доставлено', icon: '!', badge: 'bg-rose-100 text-rose-800 ring-rose-300' },
  cancelled: { label: 'Отменено', icon: '×', badge: 'bg-ink-100 text-ink-600 ring-ink-200' },
};

export function userFacingDeliveryIssue(error: string | null | undefined, status: Extract<SupplierDeliveryStatus, 'failed' | 'bounced'>): string {
  const raw = String(error ?? '').trim().toLowerCase();
  if (status === 'bounced') {
    if (/no such user|user unknown|адрес.*(не существует|не найден)|recipient.*not found/.test(raw)) return 'Не доставлено: адрес не существует';
    if (/reject|отклонил|rejected/.test(raw)) return 'Не доставлено: сервер получателя отклонил письмо';
    return 'Не доставлено: почтовый сервер вернул письмо';
  }
  if (!raw) return 'Ошибка отправки: причина не указана';
  if (/spam|нежелатель|policy|политик/.test(raw)) return 'Почтовый сервер отклонил письмо как нежелательное';
  if (/tempor|временно|unavailable|недоступ/.test(raw)) return 'Почтовый сервер временно недоступен';
  if (/reject|отклонил|rejected/.test(raw)) return 'Почтовый сервер отклонил письмо';
  return 'Ошибка отправки: не удалось завершить отправку';
}

const EMPTY_DELIVERY_COUNTS: SupplierDeliveryCounts = {
  not_sent: 0, queued: 0, accepted: 0, failed: 0, delivery_unknown: 0, bounced: 0, cancelled: 0,
};

export function deliveryCountsFor(supplier: Supplier): SupplierDeliveryCounts {
  if (supplier.delivery_counts) return supplier.delivery_counts;
  const counts = { ...EMPTY_DELIVERY_COUNTS };
  const fallback: SupplierDeliveryStatus = supplier.mail_status === 'waiting' || supplier.mail_status === 'answered'
    ? 'accepted'
    : supplier.mail_status === 'sent' ? 'queued'
      : supplier.mail_status === 'error' ? 'failed'
        : supplier.mail_status === 'delivery_unknown' ? 'delivery_unknown' : 'not_sent';
  counts[fallback] += 1;
  return counts;
}

export function responseStatusFor(supplier: Supplier): 'none' | 'waiting' | 'answered' {
  if (supplier.response_status) return supplier.response_status;
  if (supplier.mail_status === 'answered') return 'answered';
  if (supplier.mail_status === 'waiting') return 'waiting';
  return 'none';
}

function hasDelivery(supplier: Supplier, status: keyof SupplierDeliveryCounts): boolean {
  return deliveryCountsFor(supplier)[status] > 0;
}

function isNotSentCompany(supplier: Supplier): boolean {
  if (!supplier.email) return false;
  const counts = deliveryCountsFor(supplier);
  const emailCount = supplier.email_count ?? (supplier.email ? 1 : 0);
  return emailCount > 0 && counts.not_sent >= emailCount && !(['queued', 'accepted', 'failed', 'delivery_unknown', 'bounced', 'cancelled'] as const).some((status) => counts[status] > 0);
}

function hasOutbound(supplier: Supplier): boolean {
  const counts = deliveryCountsFor(supplier);
  return (['queued', 'accepted', 'failed', 'delivery_unknown', 'bounced', 'cancelled'] as const).some((status) => counts[status] > 0);
}

function deliveryStatusFor(supplier: Supplier): SupplierDeliveryStatus {
  const counts = deliveryCountsFor(supplier);
  return (Object.keys(STATUS_ORDER) as SupplierDeliveryStatus[]).find((status) => counts[status as keyof SupplierDeliveryCounts] > 0) ?? 'not_sent';
}

export function useRequestState(requestId: number | null) {
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<FilterKey>('all');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('relevance');

  const load = useCallback(() => {
    if (requestId == null) return Promise.resolve();
    return api.getRequest(requestId).then((data) => {
      setDetail(data);
      setSelectedIds(new Set());
    });
  }, [requestId]);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  const suppliers = useMemo(() => detail?.items ?? [], [detail]);
  const positionNameByKey = useMemo(() => {
    const map = new Map<string, string>();
    (detail?.positions ?? []).forEach((p) => map.set(p.position_key, p.name));
    return map;
  }, [detail]);

  const itemNames = useCallback(
    (supplier: Supplier) => supplier.position_keys.map((key) => positionNameByKey.get(key)).filter((v): v is string => Boolean(v)),
    [positionNameByKey]
  );

  const toggleSelect = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback((ids: number[]) => {
    setSelectedIds((prev) => {
      const allSelected = ids.every((id) => prev.has(id));
      const next = new Set(prev);
      ids.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelectedIds(new Set()), []);

  const toggleIrrelevant = useCallback(
    async (supplierId: number) => {
      if (requestId == null) return;
      await api.setSupplierIrrelevant(requestId, supplierId, true);
      await load();
    },
    [requestId, load]
  );

  const counts = useMemo(() => {
    const found = suppliers.length;
    const withContacts = suppliers.filter((s) => s.email).length;
    const withoutContacts = found - withContacts;
    // This is a company-card count: queued/accepted contacts are not
    // «не отправлено», even when another email on the same card is untouched.
    const notSent = suppliers.filter(isNotSentCompany).length;
    const selected = selectedIds.size;
    const queued = suppliers.filter((s) => hasDelivery(s, 'queued')).length;
    const accepted = suppliers.filter((s) => hasDelivery(s, 'accepted')).length;
    const waiting = suppliers.filter((s) => responseStatusFor(s) === 'waiting').length;
    const answered = suppliers.filter((s) => responseStatusFor(s) === 'answered').length;
    const error = suppliers.filter((s) => hasDelivery(s, 'failed')).length;
    const bounced = suppliers.filter((s) => hasDelivery(s, 'bounced')).length;
    const deliveryUnknown = suppliers.filter((s) => hasDelivery(s, 'delivery_unknown')).length;
    const outbound = suppliers.filter(hasOutbound).length;
    // Kept as a compatibility alias for consumers outside the request page;
    // it is deliberately not rendered as «отправлено» anymore.
    return { found, withContacts, withoutContacts, notSent, selected, queued, accepted, waiting, answered, error, bounced, deliveryUnknown, outbound, sent: outbound };
  }, [suppliers, selectedIds]);

  const visibleSuppliers = useMemo(() => {
    let list = suppliers;
    if (filter === 'with_contacts') list = list.filter((s) => s.email);
    else if (filter === 'without_contacts') list = list.filter((s) => !s.email);
    else if (filter === 'not_sent') list = list.filter(isNotSentCompany);
    else if (filter === 'selected') list = list.filter((s) => selectedIds.has(s.id));
    else if (filter === 'queued') list = list.filter((s) => hasDelivery(s, 'queued'));
    else if (filter === 'accepted') list = list.filter((s) => hasDelivery(s, 'accepted'));
    else if (filter === 'waiting') list = list.filter((s) => responseStatusFor(s) === 'waiting');
    else if (filter === 'answered') list = list.filter((s) => responseStatusFor(s) === 'answered');
    else if (filter === 'error') list = list.filter((s) => hasDelivery(s, 'failed'));
    else if (filter === 'bounce') list = list.filter((s) => hasDelivery(s, 'bounced'));
    else if (filter === 'delivery_unknown') list = list.filter((s) => hasDelivery(s, 'delivery_unknown'));

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((s) => s.name.toLowerCase().includes(q) || s.inn.includes(q) || s.host.toLowerCase().includes(q) || (s.email && s.email.toLowerCase().includes(q)));
    }

    const sorted = [...list];
    if (sort === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    else if (sort === 'status') sorted.sort((a, b) => STATUS_ORDER[deliveryStatusFor(a)] - STATUS_ORDER[deliveryStatusFor(b)]);
    return sorted;
  }, [suppliers, filter, search, sort, selectedIds]);

  return {
    detail,
    loading,
    suppliers,
    itemNames,
    selectedIds,
    toggleSelect,
    toggleSelectAll,
    clearSelection,
    toggleIrrelevant,
    filter,
    setFilter,
    search,
    setSearch,
    sort,
    setSort,
    counts,
    visibleSuppliers,
    reload: load,
  };
}
