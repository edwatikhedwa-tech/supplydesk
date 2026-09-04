import { Search } from 'lucide-react';
import { FILTERS, SORTS, type FilterKey, type SortKey } from '@/useRequestState';
import { Button, DropdownMenu, TextField } from '@/components/ui';

interface Props {
  filter: FilterKey;
  setFilter: (filter: FilterKey) => void;
  search: string;
  setSearch: (search: string) => void;
  sort: SortKey;
  setSort: (sort: SortKey) => void;
  counts: { found: number; withContacts: number; withoutContacts: number; notSent: number; selected: number; queued: number; accepted: number; waiting: number; answered: number; error: number; bounced: number; deliveryUnknown: number };
}

const FILTER_COUNTS: Record<FilterKey, keyof Props['counts']> = {
  all: 'found',
  with_contacts: 'withContacts',
  without_contacts: 'withoutContacts',
  not_sent: 'notSent',
  selected: 'selected',
  queued: 'queued',
  accepted: 'accepted',
  waiting: 'waiting',
  answered: 'answered',
  error: 'error',
  bounce: 'bounced',
  delivery_unknown: 'deliveryUnknown',
};

export function ListToolbar({ filter, setFilter, search, setSearch, sort, setSort, counts }: Props) {
  const currentSort = SORTS.find((item) => item.key === sort)!;
  const visibleFilters = FILTERS.filter((item) => item.key !== 'delivery_unknown' || counts.deliveryUnknown > 0 || filter === 'delivery_unknown');
  return (
    <div data-supplier-toolbar className="sticky top-14 z-10 flex flex-col gap-3 border-b border-ink-200/70 bg-ink-50 px-4 py-3 sm:px-6 lg:top-0 lg:px-10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex items-baseline gap-2"><h2 className="text-sm font-semibold text-ink-800">Компании</h2><span className="text-xs text-ink-400">· {counts.found}</span></div>
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center">
          <TextField label="Поиск компании, ИНН или сайта" icon={Search} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск компании, ИНН, сайта…" className="w-full sm:w-64" />
          <DropdownMenu label="Сортировка" items={SORTS.map((item) => ({ id: item.key, label: item.label }))} value={currentSort.key} onSelect={(value) => setSort(value as SortKey)} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Фильтр компаний">
        {visibleFilters.map((item) => {
          const active = item.key === filter;
          const count = counts[FILTER_COUNTS[item.key]];
          return <Button key={item.key} type="button" variant="ghost" size="sm" aria-pressed={active} onClick={() => setFilter(item.key)} className={active ? 'bg-ink-800 text-white hover:bg-ink-800 hover:text-white' : 'bg-ink-100/70 text-ink-600 hover:bg-ink-200/70 hover:text-ink-800'}>{item.label}<span className={active ? 'rounded-full bg-white/20 px-1.5 py-px text-2xs text-white' : 'rounded-full bg-white px-1.5 py-px text-2xs text-ink-500'}>{count}</span></Button>;
        })}
      </div>
    </div>
  );
}
