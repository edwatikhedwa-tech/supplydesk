import { useCallback, useEffect, useMemo, useState } from 'react';
import { RotateCcw, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { pluralize } from '@/lib/utils';
import { GlobalSupplierTable } from '@/components/suppliers/GlobalSupplierTable';
import { SupplierPanel } from '@/components/suppliers/SupplierPanel';
import type { BlacklistEntry, GlobalSupplierSummary } from '@/lib/types';

export function Blacklist() {
  const [suppliers, setSuppliers] = useState<GlobalSupplierSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [openId, setOpenId] = useState<number | null>(null);
  // Домены (маркетплейсы вроде Ozon по умолчанию — см. MailRepository._seed_default_blacklist)
  // блокируются ДО того, как для них вообще появляется карточка компании: у
  // домена может не быть ни ИНН, ни истории обхода. Это другая таблица
  // (blacklist_entries, а не global_supplier_blacklist), поэтому и список
  // отдельный — но восстановить их снабженец должен видеть здесь же, а не
  // только в исходном коде.
  const [domains, setDomains] = useState<BlacklistEntry[]>([]);

  const load = useCallback(() => {
    setLoading(true);
    return Promise.all([api.listGlobalSuppliers(), api.listBlacklist()])
      .then(([suppliersRes, domainsRes]) => {
        setSuppliers(suppliersRes.items);
        setDomains(domainsRes.items);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visibleDomains = useMemo(() => {
    if (!search.trim()) return domains;
    const q = search.trim().toLowerCase();
    return domains.filter((d) => d.company_name.toLowerCase().includes(q) || d.external_key.toLowerCase().includes(q));
  }, [domains, search]);

  const restoreDomain = async (entryId: number) => {
    await api.restoreBlacklist(entryId);
    await load();
  };

  const blacklisted = useMemo(() => {
    let result = suppliers.filter((s) => s.relationship_status === 'blacklisted');
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((s) => s.name.toLowerCase().includes(q) || s.inn.includes(q));
    }
    return result;
  }, [suppliers, search]);

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const ids = blacklisted.map((s) => s.id);
    const allSelected = ids.every((id) => selected.has(id));
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const restoreOne = async (id: number) => {
    await api.setGlobalSupplierRelationship(id, 'none');
    setSelected((prev) => { const next = new Set(prev); next.delete(id); return next; });
    await load();
  };

  const restoreSelected = async () => {
    await Promise.all(Array.from(selected).map((id) => api.setGlobalSupplierRelationship(id, 'none')));
    setSelected(new Set());
    await load();
  };

  return (
    <div className="min-h-screen px-6 py-7 lg:px-10 lg:py-10 pb-24 animate-fade-in">
      <div className="mx-auto max-w-[1600px]">
      <div className="mb-6">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink-400">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />Чёрный список
        </div>
        <h1 className="text-page-title font-bold">Чёрный список</h1>
        <p className="mt-1 text-sm text-ink-500">
          {blacklisted.length} {pluralize(blacklisted.length, 'поставщик', 'поставщика', 'поставщиков')}
          {domains.length > 0 && <> · {domains.length} {pluralize(domains.length, 'домен', 'домена', 'доменов')}</>}
        </p>
      </div>

      <div className="mb-5 px-4 py-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800">
        Поставщики из чёрного списка не участвуют в автопоиске и недоступны для выбора при создании новой заявки.
      </div>

      <div className="mb-5">
        <div className="relative flex-1 min-w-[240px] max-w-xs">
          <Search className="w-4 h-4 text-ink-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по названию, ИНН…"
            className="w-full pl-9 pr-3 py-2 text-sm bg-white border border-ink-200 rounded-xl text-ink-800 placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-accent-200 focus:border-accent-400 transition-all"
          />
        </div>
      </div>

      <GlobalSupplierTable
        view="blacklist"
        suppliers={blacklisted}
        loading={loading}
        emptyMessage="В чёрном списке пока никого нет. Поставщики попадают сюда, когда их отмечают вручную на карточке или через «Сообщить о проблеме»."
        selected={selected}
        onToggleSelect={toggleSelect}
        onToggleSelectAll={toggleSelectAll}
        onOpenSupplier={setOpenId}
        onRestore={restoreOne}
      />

      {visibleDomains.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-1 text-sm font-semibold text-ink-800">Домены</h2>
          <p className="mb-3 text-xs text-ink-500">
            Блокируются до появления карточки компании — обычно маркетплейсы и агрегаторы, у которых ИНН на странице товара принадлежит площадке, а не продавцу.
          </p>
          <div className="overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-soft">
            <div className="divide-y divide-ink-100">
              {visibleDomains.map((d) => (
                <div key={d.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-ink-800">{d.company_name}</div>
                    <div className="truncate text-xs text-ink-500">{d.external_key}{d.reason ? ` · ${d.reason}` : ''}</div>
                  </div>
                  <button
                    onClick={() => restoreDomain(d.id)}
                    className="inline-flex min-h-10 shrink-0 items-center gap-1.5 rounded-lg border border-ink-200 px-3 py-1.5 text-xs font-medium text-ink-600 hover:border-accent-300 hover:text-accent-700"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />Вернуть
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 lg:left-[248px] right-0 bg-white border-t border-ink-200 shadow-panel px-8 py-4 flex items-center justify-between z-30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-accent-600 flex items-center justify-center text-white text-sm font-bold">{selected.size}</div>
            <span className="text-sm text-ink-700">Выбрано <span className="font-semibold text-ink-900">{selected.size}</span> поставщиков</span>
            <button onClick={() => setSelected(new Set())} className="min-h-10 px-2 text-xs text-ink-400 transition-colors hover:text-ink-800">Снять выбор</button>
          </div>
          <button
            onClick={restoreSelected}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-accent-600 px-5 py-2.5 text-sm font-medium text-white shadow-soft transition-colors hover:bg-accent-700"
          >
            <RotateCcw className="w-4 h-4" />Вернуть выбранных
          </button>
        </div>
      )}

      {openId != null && (
        <SupplierPanel
          globalSupplierId={openId}
          onClose={() => { setOpenId(null); load(); }}
        />
      )}
      </div>
    </div>
  );
}
