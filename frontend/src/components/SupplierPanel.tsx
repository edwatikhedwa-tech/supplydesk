import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { X, Mail, Phone, Building2, ChevronRight, Globe, Send, ShieldOff } from 'lucide-react';
import type { Supplier } from '@/lib/types';
import { STATUS_META } from '@/useRequestState';
import { displaySupplierName } from '@/lib/utils';
import { RegistryFinanceRow } from '@/components/suppliers/RegistryFinanceRow';

interface Props {
  supplier: Supplier | null;
  itemNames: (supplier: Supplier) => string[];
  onClose: () => void;
  onWrite: (id: number) => void;
  onMarkIrrelevant: (id: number) => void;
}

export function SupplierPanel({ supplier, itemNames, onClose, onWrite, onMarkIrrelevant }: Props) {
  useEffect(() => {
    if (!supplier) return;
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [supplier, onClose]);

  if (!supplier) return null;
  const meta = STATUS_META[supplier.mail_status];
  // A stray "…" mid-sentence in a SERP snippet reads as broken text — trim to
  // the last full sentence/clause instead of showing the raw cut.
  const cleanReason = supplier.reason?.replace(/\s*\.{2,}\s*$/, '').trim();

  return (
    <>
      <div className="fixed inset-0 z-40 bg-ink-900/30" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[420px] max-w-[90vw] flex-col overflow-y-auto bg-white p-5 shadow-panel">
        <div className="flex justify-between">
          <div className="min-w-0">
            <h2 title={supplier.name} className="truncate font-semibold text-ink-900">{displaySupplierName(supplier.name, supplier.inn)}</h2>
            <span className={`mt-2 inline-block rounded-full px-2 py-1 text-2xs ${meta.badge}`}>{meta.label}</span>
          </div>
          <button onClick={onClose} className="shrink-0 text-ink-400 hover:text-ink-700"><X className="h-4 w-4" /></button>
        </div>

        <RegistryFinanceRow registry={supplier.registry} finances={supplier.finances} className="-mx-5 mt-4 px-5 py-2 border-y border-ink-100" />

        <div className="mt-6 space-y-3 text-sm text-ink-700">
          <p className="flex items-center gap-2"><Mail className="h-4 w-4 shrink-0 text-ink-400" />{supplier.email ?? 'Нет email'}</p>
          <p className="flex items-center gap-2"><Phone className="h-4 w-4 shrink-0 text-ink-400" />{supplier.phone || 'Нет телефона'}</p>
          {supplier.inn && (
            <p className="flex items-center gap-2">
              <Building2 className="h-4 w-4 shrink-0 text-ink-400" />ИНН {supplier.inn}
              <Link to={`/suppliers?search=${supplier.inn}`} className="ml-auto inline-flex items-center gap-0.5 text-xs font-medium text-accent-600 hover:text-accent-700">
                Карточка компании<ChevronRight className="h-3 w-3" />
              </Link>
            </p>
          )}
          <p className="flex items-center gap-2">
            <Globe className="h-4 w-4 shrink-0 text-ink-400" />
            <a href={`https://${supplier.host}`} target="_blank" rel="noreferrer" className="truncate hover:text-accent-600 hover:underline">{supplier.host}</a>
          </p>
          <div className="pt-1">
            <b className="text-xs uppercase tracking-wider text-ink-500">Позиции</b>
            <p className="mt-1.5 text-xs text-ink-600">{itemNames(supplier).join(' · ') || '—'}</p>
          </div>
          {cleanReason && (
            <div>
              <b className="text-xs uppercase tracking-wider text-ink-500">Почему найден</b>
              <p className="mt-1.5 text-xs text-ink-500">{cleanReason}</p>
            </div>
          )}
        </div>

        <div className="mt-6 space-y-2">
          <button
            disabled={!supplier.email}
            onClick={() => onWrite(supplier.id)}
            className="inline-flex w-full items-center justify-center gap-2 rounded bg-accent-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />Написать
          </button>
          <button
            onClick={() => onMarkIrrelevant(supplier.id)}
            className="inline-flex w-full items-center justify-center gap-2 rounded border border-ink-200 px-3 py-2 text-xs font-semibold text-ink-500 hover:border-rose-200 hover:text-rose-600"
          >
            <ShieldOff className="h-3.5 w-3.5" />Убрать из этой заявки
          </button>
        </div>
      </aside>
    </>
  );
}
