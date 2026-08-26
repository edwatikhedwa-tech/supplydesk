import { useState } from 'react';
import { Package } from 'lucide-react';
import { Navigate, useParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/PageHeader';
import { EditRequestModal } from '@/components/EditRequestModal';
import { ListToolbar } from '@/components/ListToolbar';
import { SupplierTable } from '@/components/SupplierTable';
import { StickyToolbar } from '@/components/StickyToolbar';
import { SupplierPanel } from '@/components/SupplierPanel';
import { Composer } from '@/components/Composer';
import { useRequestState } from '@/useRequestState';

export function RequestPage() {
  const { id } = useParams<{ id: string }>();
  const requestId = id ? Number(id) : null;
  const state = useRequestState(requestId);
  const [openSupplierId, setOpenSupplierId] = useState<number | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  if (!requestId || Number.isNaN(requestId)) return <Navigate to="/requests" replace />;
  if (state.loading) return <div className="flex min-h-screen items-center justify-center text-sm text-ink-400">Загрузка…</div>;
  if (!state.detail) return <Navigate to="/requests" replace />;

  const openSupplier = state.suppliers.find((supplier) => supplier.id === openSupplierId) ?? null;
  const handleWriteSupplier = (supplierId: number) => {
    setOpenSupplierId(null);
    if (!state.selectedIds.has(supplierId)) state.toggleSelect(supplierId);
    setComposerOpen(true);
  };
  const handleMarkIrrelevant = async (supplierId: number) => {
    setOpenSupplierId(null);
    await state.toggleIrrelevant(supplierId);
  };
  const handleRetrySearch = async () => {
    await api.startRequestSearch(requestId);
    await state.reload();
  };

  return (
    <div className="min-h-screen bg-ink-50/60 animate-fade-in">
      <PageHeader request={state.detail.request} counts={state.counts} onRetrySearch={handleRetrySearch} onEdit={() => setEditOpen(true)} />
      <main className="mx-auto max-w-[1600px]">
        {state.detail.positions.length > 0 && (
          <div className="px-6 pt-5 lg:px-10">
            <div className="flex items-center gap-1.5 mb-2 text-xs font-medium text-ink-500 uppercase tracking-wider">
              <Package className="w-3.5 h-3.5" />Позиции заявки
            </div>
            <div className="flex flex-wrap gap-1.5">
              {state.detail.positions.map((position) => (
                <span
                  key={position.position_key}
                  className="inline-flex items-baseline gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-white border border-ink-200 text-ink-700"
                >
                  {position.name}
                </span>
              ))}
            </div>
          </div>
        )}
        <ListToolbar filter={state.filter} setFilter={state.setFilter} search={state.search} setSearch={state.setSearch} sort={state.sort} setSort={state.setSort} counts={state.counts} />
        <SupplierTable
          suppliers={state.visibleSuppliers}
          itemNames={state.itemNames}
          totalPositions={state.detail.positions.length}
          selectedIds={state.selectedIds}
          recentlyChanged={state.recentlyChanged}
          onToggleSelect={state.toggleSelect}
          onToggleSelectAll={state.toggleSelectAll}
          onOpenSupplier={setOpenSupplierId}
          onWriteSupplier={handleWriteSupplier}
        />
      </main>
      {!composerOpen && <StickyToolbar count={state.counts.selected} onPrepare={() => setComposerOpen(true)} onClear={state.clearSelection} />}
      <SupplierPanel supplier={openSupplier} itemNames={state.itemNames} onClose={() => setOpenSupplierId(null)} onWrite={handleWriteSupplier} onMarkIrrelevant={handleMarkIrrelevant} />
      <Composer
        open={composerOpen}
        suppliers={state.suppliers}
        selectedIds={state.selectedIds}
        onClose={() => setComposerOpen(false)}
        onSend={async (ids, subject, body) => {
          await state.sendRequests(ids, subject, body);
          state.clearSelection();
        }}
      />
      {editOpen && (
        <EditRequestModal
          request={state.detail.request}
          onClose={() => setEditOpen(false)}
          onSaved={state.reload}
        />
      )}
    </div>
  );
}
