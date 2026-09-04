import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Send } from 'lucide-react';
import { api } from '@/lib/api';
import { pluralize } from '@/lib/utils';
import { PageFrame, PageIntro } from '@/components/PageFrame';
import { Button, TextField } from '@/components/ui';
import { GlobalSupplierTable } from '@/components/suppliers/GlobalSupplierTable';
import { SupplierPanel } from '@/components/suppliers/SupplierPanel';
import type { GlobalSupplierSummary } from '@/lib/types';

// 'never_replied' and 'not_contacted' used to be the same bucket
// (total_requests === 0 OR response_rate === 0) — conflated "never wrote to
// them" with "wrote and got silence", which are different states worth
// different follow-up. Split per the audit finding.
type Filter = 'all' | 'favorite' | 'blacklisted' | 'stale' | 'never_replied' | 'not_contacted';

const filterConfig: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'favorite', label: 'Избранные' },
  { key: 'blacklisted', label: 'Чёрный список' },
  { key: 'stale', label: 'Давно не было контакта' },
  { key: 'never_replied', label: 'Не отвечают' },
  { key: 'not_contacted', label: 'Не контактировали' },
];

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

export function Suppliers() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [suppliers, setSuppliers] = useState<GlobalSupplierSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const filter = (searchParams.get('filter') as Filter) || 'all';
  // Also readable from the URL (?search=<inn>) so other screens (e.g. a
  // host-based supplier panel) can deep-link straight to a company's CRM card.
  const [search, setSearch] = useState(() => searchParams.get('search') || '');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  // ?open=<global_supplier_id> — открывает карточку сразу при заходе на
  // страницу. Так на неё можно сослаться прямой ссылкой (например, из окна
  // отправки письма — «Открыть карточку компании» в новой вкладке).
  const [openId, setOpenId] = useState<number | null>(() => {
    const raw = searchParams.get('open');
    return raw ? Number(raw) : null;
  });

  const load = useCallback(() => {
    setLoading(true);
    return api
      .listGlobalSuppliers()
      .then((res) => setSuppliers(res.items))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setFilter = (f: Filter) => setSearchParams(f === 'all' ? {} : { filter: f });

  const filtered = useMemo(() => {
    let result = [...suppliers];
    if (filter === 'favorite') result = result.filter((s) => s.relationship_status === 'favorite');
    if (filter === 'blacklisted') result = result.filter((s) => s.relationship_status === 'blacklisted');
    if (filter === 'stale') result = result.filter((s) => { const d = daysSince(s.last_contact_at); return d !== null && d > 14; });
    if (filter === 'never_replied') result = result.filter((s) => s.total_requests > 0 && s.response_rate === 0);
    if (filter === 'not_contacted') result = result.filter((s) => s.total_requests === 0);

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((s) => s.name.toLowerCase().includes(q) || s.inn.includes(q) || s.site.toLowerCase().includes(q));
    }

    result.sort((a, b) => {
      const aDate = a.last_contact_at ? new Date(a.last_contact_at).getTime() : 0;
      const bDate = b.last_contact_at ? new Date(b.last_contact_at).getTime() : 0;
      if (bDate !== aDate) return bDate - aDate;
      if (b.total_requests !== a.total_requests) return b.total_requests - a.total_requests;
      return b.response_rate - a.response_rate;
    });
    return result;
  }, [suppliers, filter, search]);

  const counts = useMemo(
    () => ({
      all: suppliers.length,
      favorite: suppliers.filter((s) => s.relationship_status === 'favorite').length,
      blacklisted: suppliers.filter((s) => s.relationship_status === 'blacklisted').length,
      stale: suppliers.filter((s) => { const d = daysSince(s.last_contact_at); return d !== null && d > 14; }).length,
      never_replied: suppliers.filter((s) => s.total_requests > 0 && s.response_rate === 0).length,
      not_contacted: suppliers.filter((s) => s.total_requests === 0).length,
    }) as Record<Filter, number>,
    [suppliers],
  );

  const toggleSelect = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    const ids = filtered.map((s) => s.id);
    const allSelected = ids.every((id) => selected.has(id));
    setSelected((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (allSelected ? next.delete(id) : next.add(id)));
      return next;
    });
  };

  const createRequestWithSelected = () => {
    navigate(`/requests/new?suppliers=${Array.from(selected).join(',')}`);
  };

  return (
    <PageFrame className="pb-24">
      <div>
      <PageIntro eyebrow="Справочник поставщиков" title="Поставщики" description={`${suppliers.length} ${pluralize(suppliers.length, 'поставщик', 'поставщика', 'поставщиков')} в базе`} />

      <div className="flex items-center gap-3 mb-5 flex-wrap">
        <div className="flex items-center gap-1.5 bg-white border border-ink-200 rounded-xl p-1 shadow-soft flex-wrap">
          {filterConfig.map((f) => (
            <button
              key={f.key}
              type="button"
              aria-pressed={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={`min-h-10 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filter === f.key ? 'bg-accent-600 text-white' : 'text-ink-500 hover:text-ink-800 hover:bg-ink-50'
              }`}
            >
              {f.label}
              <span className={`ml-1.5 ${filter === f.key ? 'text-accent-200' : 'text-ink-400'}`}>{counts[f.key]}</span>
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[240px] max-w-xs">
          <TextField
            id="suppliers-search"
            label="Поиск по названию, ИНН или сайту"
            icon={Search}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Поиск по названию, ИНН, сайту…"
          />
        </div>
      </div>

      <GlobalSupplierTable
        view="all"
        suppliers={filtered}
        loading={loading}
        emptyMessage="Найдено 0 поставщиков. Попробуйте изменить запрос или сбросить фильтры"
        selected={selected}
        onToggleSelect={toggleSelect}
        onToggleSelectAll={toggleSelectAll}
        onOpenSupplier={setOpenId}
      />

      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 lg:left-[248px] right-0 bg-white border-t border-ink-200 shadow-panel px-8 py-4 flex items-center justify-between z-30">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-accent-600 flex items-center justify-center text-white text-sm font-bold">{selected.size}</div>
            <span className="text-sm text-ink-700">Выбрано <span className="font-semibold text-ink-900">{selected.size}</span> поставщиков</span>
            <Button onClick={() => setSelected(new Set())} variant="ghost" size="sm" className="ml-2">Снять выбор</Button>
          </div>
          <Button
            onClick={createRequestWithSelected}
            variant="primary"
          >
            <Send className="w-4 h-4" />Создать заявку с выбранными
          </Button>
        </div>
      )}

      {openId != null && (
        <SupplierPanel
          globalSupplierId={openId}
          onClose={() => { setOpenId(null); load(); }}
        />
      )}
      </div>
    </PageFrame>
  );
}
