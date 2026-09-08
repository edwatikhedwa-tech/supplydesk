import { Link2, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { ManualLinkRequestOption } from '../lib/types';
import { Modal } from './ui/Modal';

export function ManualLinkModal({
  inboxMessageId,
  onClose,
  onLinked,
}: {
  inboxMessageId: number;
  onClose: () => void;
  onLinked: () => void;
}) {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<ManualLinkRequestOption[] | null>(null);
  const [linkingId, setLinkingId] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const handle = setTimeout(() => {
      api
        .listManualLinkRequests(query)
        .then((res) => setItems(res.items))
        .catch(() => setItems([]));
    }, 200);
    return () => clearTimeout(handle);
  }, [query]);

  async function link(requestId: number) {
    setError('');
    setLinkingId(requestId);
    try {
      await api.manualLinkInboxMessage({ inbox_message_id: inboxMessageId, request_id: requestId, confirmed: true });
      onLinked();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось связать письмо с заявкой.');
      setLinkingId(null);
    }
  }

  return (
    <Modal title="Связать письмо с заявкой" onClose={onClose} width={480}>
      <div className="space-y-3">
        <div className="relative">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Поиск заявки по названию…"
            className="h-9 w-full rounded-md border border-border-strong bg-surface pl-8 pr-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>

        {error && <p className="text-[12px] text-danger">{error}</p>}

        <div className="max-h-[320px] overflow-y-auto rounded-md border border-border">
          {items === null ? (
            <p className="px-3 py-3 text-[12.5px] text-ink-muted">Загружаем…</p>
          ) : items.length === 0 ? (
            <p className="px-3 py-3 text-[12.5px] text-ink-muted">Заявки не найдены.</p>
          ) : (
            items.map((item) => (
              <button
                key={item.id}
                onClick={() => void link(item.id)}
                disabled={linkingId !== null}
                className="flex w-full items-center gap-2.5 border-b border-border px-3 py-2.5 text-left last:border-0 hover:bg-surface-hover disabled:opacity-50"
              >
                <Link2 size={14} className="shrink-0 text-ink-faint" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12.5px] font-medium text-ink">{item.name}</p>
                  <p className="truncate text-[11px] text-ink-faint">
                    №{item.id}
                    {item.supplier_names.length > 0 ? ` · ${item.supplier_names.join(', ')}` : ''}
                  </p>
                </div>
                {linkingId === item.id && <span className="shrink-0 text-[11px] text-ink-faint">Связываем…</span>}
              </button>
            ))
          )}
        </div>
      </div>
    </Modal>
  );
}
