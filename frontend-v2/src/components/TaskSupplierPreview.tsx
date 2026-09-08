import { ExternalLink, Mail, Phone } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { companyAge, formatCompanyName, formatPercent } from '../lib/format';
import { useApiData } from '../lib/useApiData';

/** Compact inline company card shown under a task when it's expanded --
 * saves a navigation round-trip just to remember who a task is about. */
export function TaskSupplierPreview({ supplierId }: { supplierId: number }) {
  const state = useApiData(() => api.getGlobalSupplierDetail(supplierId), [supplierId]);

  if (state.status === 'loading') {
    return <div className="mt-1.5 rounded-md border border-border bg-canvas px-2.5 py-2 text-[11.5px] text-ink-faint">Загружаем карточку…</div>;
  }
  if (state.status === 'error') {
    return <div className="mt-1.5 rounded-md border border-danger-border bg-danger-subtle px-2.5 py-2 text-[11.5px] text-danger">Не удалось загрузить карточку.</div>;
  }

  const s = state.data;
  const age = companyAge(s.registry?.registered_at);

  return (
    <div className="mt-1.5 rounded-md border border-border bg-canvas p-2.5 text-[11.5px]">
      <div className="flex items-start justify-between gap-2">
        <Link to={`/suppliers/${s.id}`} className="min-w-0 truncate font-medium text-ink hover:text-accent hover:underline">
          {formatCompanyName(s.name)}
        </Link>
        {s.registry && (
          <span className={`shrink-0 ${s.registry.is_active === false ? 'text-danger' : 'text-success'}`}>
            {s.registry.is_active === false ? 'Ликвидировано' : 'Действует'}
          </span>
        )}
      </div>
      <p className="mt-0.5 text-ink-faint">ИНН {s.inn}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-soft">
        {s.email && (
          <a href={`mailto:${s.email}`} onClick={(e) => e.stopPropagation()} className="flex items-center gap-1 hover:text-accent">
            <Mail size={11} /> {s.email}
          </a>
        )}
        {s.phone && (
          <span className="flex items-center gap-1">
            <Phone size={11} /> {s.phone}
          </span>
        )}
        {s.site && (
          <a
            href={s.site.startsWith('http') ? s.site : `https://${s.site}`}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-accent hover:underline"
          >
            {s.site} <ExternalLink size={9} />
          </a>
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-ink-faint">
        {age && <span>Возраст: {age}</span>}
        <span>Заявок: {s.total_requests}</span>
        {s.total_requests > 0 && <span>Отклик: {formatPercent(s.response_rate / 100)}</span>}
      </div>
    </div>
  );
}
