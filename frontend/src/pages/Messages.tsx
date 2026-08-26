import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Mail, Reply, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatFullDate, formatRelativeDate } from '@/lib/utils';
import { ThreadList } from '@/components/mail/ThreadList';
import { ThreadDetail } from '@/components/mail/ThreadDetail';
import { Composer, type MailComposerContext } from '@/components/mail/Composer';
import { EmailRenderer } from '@/components/mail/EmailRenderer';
import type { InboxMessage, MailMessage, ThreadSummary } from '@/lib/types';

type Mode = 'requests' | 'unmatched';

export function Messages() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>('requests');
  const [selectedThread, setSelectedThread] = useState<ThreadSummary | null>(null);
  const [composerCtx, setComposerCtx] = useState<MailComposerContext | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const state = location.state as { composer?: MailComposerContext } | null;
    if (state?.composer) {
      setComposerCtx(state.composer);
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location, navigate]);

  const handleReply = useCallback((thread: ThreadSummary, lastMessage: MailMessage | null) => {
    const subject = thread.subject.startsWith('Re:') ? thread.subject : `Re: ${thread.subject}`;
    setComposerCtx({
      requestId: thread.request_id,
      requestName: thread.request_name,
      supplierId: thread.supplier_id,
      supplierName: thread.supplier_name,
      to: lastMessage?.direction === 'inbound' ? lastMessage.from_email : thread.supplier_email,
      subject,
    });
  }, []);

  const handleSent = () => setRefreshKey((k) => k + 1);

  return (
    <div className="flex-1 flex flex-col overflow-hidden h-screen">
      <div className="h-[76px] border-b border-ink-200/70 bg-white flex items-center justify-between px-8 shrink-0">
        <div>
          <h1 className="text-[22px] font-bold tracking-tight text-ink-900">Переписка</h1>
          <p className="text-xs text-ink-500 mt-0.5">Треды по заявкам и письма без привязки</p>
        </div>
        <div className="flex items-center bg-ink-100 rounded-lg p-0.5">
          <button
            onClick={() => setMode('requests')}
            className={cn('px-4 py-1.5 text-sm font-medium rounded-md transition-all', mode === 'requests' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-700')}
          >
            По заявкам
          </button>
          <button
            onClick={() => setMode('unmatched')}
            className={cn('px-4 py-1.5 text-sm font-medium rounded-md transition-all', mode === 'unmatched' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-700')}
          >
            Без привязки
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {mode === 'requests' ? (
          <>
            <ThreadList
              key={refreshKey}
              selectedThreadKey={selectedThread ? `${selectedThread.request_id}:${selectedThread.supplier_id}` : null}
              onSelectThread={setSelectedThread}
              refreshKey={refreshKey}
            />
            {selectedThread ? (
              <ThreadDetail
                thread={selectedThread}
                onBack={() => setSelectedThread(null)}
                onReply={handleReply}
                onOpenRequest={(requestId) => navigate(`/requests/${requestId}`)}
              />
            ) : (
              <EmptyState />
            )}
          </>
        ) : (
          <UnmatchedInbox />
        )}
      </div>

      {composerCtx && <Composer context={composerCtx} onClose={() => setComposerCtx(null)} onSent={handleSent} />}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center bg-ink-50/50 text-center px-6">
      <div className="w-16 h-16 rounded-2xl bg-white border border-ink-200 flex items-center justify-center mb-4 shadow-sm">
        <Mail size={28} className="text-ink-300" />
      </div>
      <p className="text-sm font-medium text-ink-500">Выберите письмо, чтобы прочитать его</p>
    </div>
  );
}

function UnmatchedInbox() {
  const [items, setItems] = useState<InboxMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<InboxMessage | null>(null);
  const [replyOpen, setReplyOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [sending, setSending] = useState(false);

  useEffect(() => {
    api
      .listInbox()
      .then((res) => setItems(res.items))
      .finally(() => setLoading(false));
  }, []);

  const visibleItems = search.trim()
    ? items.filter((m) => {
        const q = search.trim().toLowerCase();
        return m.from_email.toLowerCase().includes(q) || m.subject.toLowerCase().includes(q);
      })
    : items;

  const openMessage = (msg: InboxMessage) => {
    setSelected(msg);
    setReplyOpen(false);
    setSubject(msg.subject.startsWith('Re:') ? msg.subject : `Re: ${msg.subject}`);
  };

  const editorId = 'unmatched-reply-editor';

  const sendReply = async () => {
    if (!selected) return;
    setSending(true);
    try {
      const editor = document.getElementById(editorId);
      await api.replyToInbox({ inbox_message_id: selected.id, subject, body: editor?.innerHTML || '' });
      setReplyOpen(false);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <div className="w-[360px] shrink-0 border-r border-ink-200 bg-white flex flex-col">
        <div className="px-3 pt-3 pb-2.5 border-b border-ink-100 shrink-0">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по отправителю или теме…"
              className="w-full pl-9 pr-3 py-2 text-sm bg-ink-50 border border-ink-200 rounded-lg focus:outline-none focus:border-ink-300 focus:bg-white transition-colors placeholder:text-ink-400"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-6 text-center text-sm text-ink-400">
            <Loader2 size={18} className="animate-spin mx-auto" />
          </div>
        ) : visibleItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <Mail size={32} className="text-ink-300 mb-3" />
            <p className="text-sm text-ink-400">{search.trim() ? 'Ничего не найдено' : 'Нет писем без привязки к заявке'}</p>
          </div>
        ) : (
          visibleItems.map((msg) => (
            <button
              key={msg.id}
              onClick={() => openMessage(msg)}
              className={cn('w-full px-3 py-2.5 text-left border-l-2 transition-colors', selected?.id === msg.id ? 'bg-accent-50/50 border-accent-500' : 'border-transparent hover:bg-ink-50')}
            >
              <div className="flex items-center justify-between gap-2 mb-0.5">
                <span className="text-sm truncate font-medium text-ink-700">{msg.from_email}</span>
                <span className="text-[11px] text-ink-400 shrink-0">{formatRelativeDate(msg.received_at)}</span>
              </div>
              <p className="text-[13px] truncate text-ink-600">{msg.subject}</p>
            </button>
          ))
        )}
        </div>
      </div>

      {selected ? (
        <div className="flex-1 flex flex-col bg-white overflow-hidden">
          <div className="px-5 py-3.5 border-b border-ink-100 shrink-0 flex items-center gap-3">
            <button onClick={() => setSelected(null)} className="p-1.5 -ml-1.5 text-ink-500 hover:text-ink-900 hover:bg-ink-100 rounded-lg">
              <ArrowLeft size={18} />
            </button>
            <h2 className="text-base font-semibold text-ink-900 truncate flex-1">{selected.subject}</h2>
            <button
              onClick={() => setReplyOpen((v) => !v)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-ink-700 bg-ink-50 hover:bg-ink-100 rounded-lg"
            >
              <Reply size={15} />
              Ответить
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-2xl mx-auto px-5 py-4 space-y-3">
              <div className="text-xs text-ink-400">{selected.from_email} · {formatFullDate(selected.received_at)}</div>
              <EmailRenderer html={selected.body_html} text={selected.body_text} />

              {replyOpen && (
                <div className="border border-ink-200 rounded-lg overflow-hidden mt-4">
                  <div id={editorId} contentEditable suppressContentEditableWarning className="min-h-[120px] px-3 py-2.5 text-sm outline-none" />
                  <div className="flex justify-end px-3 py-2 border-t border-ink-100 bg-ink-50">
                    <button
                      onClick={sendReply}
                      disabled={sending}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-accent-600 hover:bg-accent-700 rounded-lg disabled:opacity-50"
                    >
                      {sending && <Loader2 size={14} className="animate-spin" />}
                      Отправить ответ
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <EmptyState />
      )}
    </>
  );
}
