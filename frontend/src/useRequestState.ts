import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api';
import type { RequestDetail, Supplier, SupplierMailStatus } from '@/lib/types';

export type FilterKey = 'all' | 'with_contacts' | 'producers' | 'without_contacts' | 'selected' | 'sent' | 'waiting' | 'answered';
export const FILTERS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'with_contacts', label: 'С контактами' },
  { key: 'producers', label: 'Производители' },
  { key: 'without_contacts', label: 'Без контакта' },
  { key: 'selected', label: 'Выбранные' },
  { key: 'sent', label: 'Отправлено' },
  { key: 'waiting', label: 'Ждём ответа' },
  { key: 'answered', label: 'Получен ответ' },
];

export type SortKey = 'relevance' | 'name' | 'status';
export const SORTS: { key: SortKey; label: string }[] = [
  { key: 'relevance', label: 'По релевантности' },
  { key: 'name', label: 'По названию' },
  { key: 'status', label: 'По статусу' },
];

const STATUS_ORDER: Record<SupplierMailStatus, number> = { answered: 0, waiting: 1, sent: 2, error: 3, not_sent: 4 };

export const STATUS_META: Record<SupplierMailStatus, { label: string; icon: string; dot: string; badge: string }> = {
  not_sent: { label: 'Не отправлен', icon: '○', dot: 'text-ink-400', badge: 'bg-ink-100 text-ink-600 ring-ink-200' },
  sent: { label: 'Отправлен', icon: '↗', dot: 'text-accent-600', badge: 'bg-accent-50 text-accent-700 ring-accent-200' },
  waiting: { label: 'Ждём ответ', icon: '◷', dot: 'text-amber-600', badge: 'bg-amber-50 text-amber-700 ring-amber-200' },
  answered: { label: 'Ответ получен', icon: '●', dot: 'text-emerald-600', badge: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  error: { label: 'Ошибка', icon: '!', dot: 'text-rose-600', badge: 'bg-rose-50 text-rose-700 ring-rose-200' },
};

export function useRequestState(requestId: number | null) {
  const [detail, setDetail] = useState<RequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<FilterKey>('all');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortKey>('relevance');
  const [recentlyChanged, setRecentlyChanged] = useState<Set<number>>(new Set());

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

  const suppliers = detail?.items ?? [];
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

  const sendRequests = useCallback(
    async (ids: number[], subject: string, body: string) => {
      if (requestId == null) return;
      const targets = suppliers.filter((s) => ids.includes(s.id) && s.email);
      await api.sendMailBulk({
        request_id: requestId,
        suppliers: targets.map((s) => ({ id: s.id, email: s.email as string, name: s.name })),
        subject,
        body,
      });
      setRecentlyChanged(new Set(ids));
      await load();
    },
    [requestId, suppliers, load]
  );

  const counts = useMemo(() => {
    const found = suppliers.length;
    const withContacts = suppliers.filter((s) => s.email).length;
    const withoutContacts = found - withContacts;
    // Роль берётся из основного ОКВЭД компании в ЕГРЮЛ (checko_client.classify_okved),
    // поэтому это не догадка по названию сайта: для закупщика «завод или перекупщик» —
    // главный вопрос, а данные для ответа уже собираются.
    const producers = suppliers.filter((s) => s.role === 'производитель').length;
    const selected = selectedIds.size;
    const sent = suppliers.filter((s) => s.mail_status === 'sent').length;
    const waiting = suppliers.filter((s) => s.mail_status === 'waiting').length;
    const answered = suppliers.filter((s) => s.mail_status === 'answered').length;
    return { found, withContacts, producers, withoutContacts, selected, sent, waiting, answered };
  }, [suppliers, selectedIds]);

  const visibleSuppliers = useMemo(() => {
    let list = suppliers;
    if (filter === 'with_contacts') list = list.filter((s) => s.email);
    else if (filter === 'producers') list = list.filter((s) => s.role === 'производитель');
    else if (filter === 'without_contacts') list = list.filter((s) => !s.email);
    else if (filter === 'selected') list = list.filter((s) => selectedIds.has(s.id));
    else if (filter === 'sent') list = list.filter((s) => s.mail_status === 'sent');
    else if (filter === 'waiting') list = list.filter((s) => s.mail_status === 'waiting');
    else if (filter === 'answered') list = list.filter((s) => s.mail_status === 'answered');

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter((s) => s.name.toLowerCase().includes(q) || s.inn.includes(q) || s.host.toLowerCase().includes(q) || (s.email && s.email.toLowerCase().includes(q)));
    }

    const sorted = [...list];
    if (sort === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
    else if (sort === 'status') sorted.sort((a, b) => STATUS_ORDER[a.mail_status] - STATUS_ORDER[b.mail_status]);
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
    sendRequests,
    recentlyChanged,
    counts,
    visibleSuppliers,
    reload: load,
  };
}
