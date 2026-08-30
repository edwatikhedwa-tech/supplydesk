import { useCallback, useEffect, useState } from 'react';
import { Package } from 'lucide-react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { ApiError, api } from '@/lib/api';
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
  const navigate = useNavigate();
  const state = useRequestState(requestId);
  const [openSupplierId, setOpenSupplierId] = useState<number | null>(null);
  const closeSupplier = useCallback(() => setOpenSupplierId(null), []);
  const [composerOpen, setComposerOpen] = useState(false);
  const closeComposer = useCallback(() => setComposerOpen(false), []);
  const [editOpen, setEditOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const requestStatus = state.detail?.request.status;
  const reloadRequest = state.reload;

  // Vercel may recycle the function after the start response, so search work
  // is advanced by short, durable API steps while the request is open. Each
  // step has a server-side lease and is safe to retry after an interruption.
  useEffect(() => {
    if (!requestId || requestStatus !== 'searching') return undefined;
    let cancelled = false;
    let busy = false;
    const tick = async () => {
      if (cancelled || busy) return;
      busy = true;
      try {
        await api.stepRequestSearch(requestId);
        if (!cancelled) await reloadRequest();
      } catch {
        // The next tick retries transient network/function failures. A
        // permanent search error is persisted by the API and ends the loop.
      } finally {
        busy = false;
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 1500);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [requestId, requestStatus, reloadRequest]);

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
  const handleDeleteRequest = async () => {
    if (!window.confirm(`Удалить заявку «${state.detail?.request.name ?? ''}»? Все результаты поиска и переписка по ней будут удалены.`)) return;
    setDeleteError('');
    setDeleting(true);
    try {
      await api.deleteRequest(requestId);
      navigate('/requests', { replace: true });
    } catch (error) {
      setDeleteError(error instanceof ApiError ? error.message : 'Не удалось удалить заявку. Попробуйте ещё раз.');
      setDeleting(false);
    }
  };

  return (
    <div className="min-h-screen overflow-x-hidden bg-ink-50 animate-fade-in">
      <PageHeader request={state.detail.request} counts={state.counts} onRetrySearch={handleRetrySearch} onEdit={() => setEditOpen(true)} onDelete={handleDeleteRequest} deleting={deleting} onCompose={() => setComposerOpen(true)} />
      {deleteError && <div role="alert" className="mx-auto max-w-[1600px] px-6 pt-4 text-sm font-medium text-rose-700 lg:px-10">{deleteError}</div>}
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
          onToggleSelect={state.toggleSelect}
          onToggleSelectAll={state.toggleSelectAll}
          onOpenSupplier={setOpenSupplierId}
          onWriteSupplier={handleWriteSupplier}
          onOpenThread={(supplierId) => navigate(`/messages?thread=${requestId}:${supplierId}`)}
        />
      </main>
      {!composerOpen && <StickyToolbar count={state.counts.selected} onPrepare={() => setComposerOpen(true)} onClear={state.clearSelection} />}
      <SupplierPanel
        supplier={openSupplier}
        requestId={requestId}
        itemNames={state.itemNames}
        onClose={closeSupplier}
        onWrite={handleWriteSupplier}
        onMarkIrrelevant={handleMarkIrrelevant}
        onSupplierUpdated={state.reload}
      />
      <Composer
        open={composerOpen}
        requestId={requestId}
        suppliers={state.suppliers}
        selectedIds={state.selectedIds}
        onClose={closeComposer}
        onCampaignCreated={(campaignId) => {
          state.clearSelection();
          navigate(`/mail/campaigns/${campaignId}`);
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
