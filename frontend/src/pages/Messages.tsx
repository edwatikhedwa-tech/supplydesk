import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, Link as LinkIcon, Loader2, Mail, RefreshCw, Reply, Search, X } from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { cn, formatFullDate, formatRelativeDate } from '@/lib/utils';
import { ThreadList } from '@/components/mail/ThreadList';
import { OutboxList } from '@/components/mail/OutboxList';
import { ThreadDetail } from '@/components/mail/ThreadDetail';
import { Composer, type MailComposerContext } from '@/components/mail/Composer';
import { EmailRenderer } from '@/components/mail/EmailRenderer';
import { InboxReplyComposer } from '@/components/mail/InboxReplyComposer';
import type { InboxMessage, InboxSuggestion, MailMessage, ManualLinkRequestOption, ThreadSummary } from '@/lib/types';

type Mode = 'requests' | 'unmatched' | 'outbox';

function threadKey(thread: ThreadSummary): string {
  return thread.manual_inbox_id != null
    ? `manual:${thread.manual_inbox_id}`
    : `${thread.request_id}:${thread.supplier_id}`;
}

export function Messages() {
  const navigate = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState<Mode>('requests');
  const [selectedThread, setSelectedThread] = useState<ThreadSummary | null>(null);
  const [composerCtx, setComposerCtx] = useState<MailComposerContext | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  /** Открыть конкретный тред по ссылке `/messages?thread=<заявка>:<поставщик>`.
   *  Так статус «Ответ получен» в таблице заявки ведёт прямо в письмо, а не
   *  в общий список, где его ещё нужно найти. Ждём загрузку списка тредов,
   *  потому что ThreadDetail принимает объект треда, а не пару id. */
  useEffect(() => {
    const wanted = new URLSearchParams(location.search).get('thread');
    if (!wanted) return;
    const [requestId, supplierId] = wanted.split(':').map(Number);
    if (!requestId || !supplierId) return;
    let cancelled = false;
    api.listThreads().then((res) => {
      if (cancelled) return;
      const found = res.items.find((t) => t.request_id === requestId && t.supplier_id === supplierId);
      if (found) {
        setMode('requests');
        setSelectedThread(found);
      }
      // Параметр убираем, чтобы возврат «назад» не открывал тред заново.
      navigate('/messages', { replace: true });
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [location.search, navigate]);

  /** Открыть конкретное неразобранное письмо по ссылке
   *  `/messages?tab=unmatched&inbox=<id>` — с дашборда и из счётчика в
   *  навигации, чтобы «без привязки» вело сразу в письмо, а не в список,
   *  который ещё нужно пролистать. */
  const params = new URLSearchParams(location.search);
  const wantedTab = params.get('tab');
  const wantedInboxId = params.get('inbox') ? Number(params.get('inbox')) : null;
  useEffect(() => {
    if (wantedTab === 'unmatched') {
      setMode('unmatched');
      setSelectedThread(null);
    }
  }, [wantedTab]);

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

  const changeMode = (nextMode: Mode) => {
    setMode(nextMode);
    setSelectedThread(null);
  };

  /** Открытие треда помечает его входящие прочитанными на сервере
   *  (MailRepository.thread_messages), поэтому список нужно перезапросить —
   *  иначе отметка «непрочитано» гасла бы только после F5. Обновляем после
   *  того, как ThreadDetail успел загрузить письма и проставить отметки. */
  const handleThreadRead = useCallback(() => setRefreshKey((k) => k + 1), []);

  const handleManualUnlink = useCallback(async (inboxMessageId: number) => {
    await api.unlinkManualInboxMessage(inboxMessageId);
    setSelectedThread(null);
    setMode('unmatched');
    setRefreshKey((k) => k + 1);
    window.dispatchEvent(new CustomEvent('supplydesk:unmatched-mail-changed', { detail: { delta: 1 } }));
  }, []);

  return (
    <div className="flex-1 flex flex-col overflow-hidden h-screen">
      <div className="flex min-h-[76px] shrink-0 flex-wrap items-center justify-between gap-3 border-b border-ink-200/70 bg-white px-4 py-3 sm:h-[76px] sm:flex-nowrap sm:px-8 sm:py-0">
        <div className="min-w-0">
          <h1 className="text-page-title font-bold text-ink-900">Переписка</h1>
          <p className="text-xs text-ink-500 mt-0.5">Переписка по заявкам, очередь отправки и письма без привязки</p>
        </div>
        <div className="flex items-center bg-ink-100 rounded-lg p-0.5">
          <button
            type="button"
            aria-pressed={mode === 'requests'}
            onClick={() => changeMode('requests')}
            className={cn('min-h-10 px-4 py-1.5 text-sm font-medium rounded-md transition-all', mode === 'requests' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-600 hover:text-ink-800')}
          >
            По заявкам
          </button>
          <button
            type="button"
            aria-pressed={mode === 'unmatched'}
            onClick={() => changeMode('unmatched')}
            className={cn('min-h-10 px-4 py-1.5 text-sm font-medium rounded-md transition-all', mode === 'unmatched' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-600 hover:text-ink-800')}
          >
            Без привязки
          </button>
          <button
            type="button"
            aria-pressed={mode === 'outbox'}
            onClick={() => changeMode('outbox')}
            className={cn('min-h-10 px-4 py-1.5 text-sm font-medium rounded-md transition-all', mode === 'outbox' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-600 hover:text-ink-800')}
          >
            Очередь
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {mode === 'requests' ? (
          <>
            {/* Без key={refreshKey}: перезагрузку списка уже делает сам
                ThreadList по изменению refreshKey, а пересоздание компонента
                вдобавок сбрасывало бы свёрнутые группы при каждом обновлении. */}
            <ThreadList
              selectedThreadKey={selectedThread ? threadKey(selectedThread) : null}
              onSelectThread={setSelectedThread}
              refreshKey={refreshKey}
            />
            {selectedThread ? (
              <ThreadDetail
                thread={selectedThread}
                onBack={() => setSelectedThread(null)}
                onReply={selectedThread.manual_inbox_id == null ? handleReply : undefined}
                onOpenRequest={(requestId) => navigate(`/requests/${requestId}`)}
                onUnlinkManual={selectedThread.manual_inbox_id != null ? handleManualUnlink : undefined}
                onRead={handleThreadRead}
              />
            ) : (
              <EmptyState className="hidden xl:flex" />
            )}
          </>
        ) : mode === 'outbox' ? (
          <>
            <OutboxList
              selectedThreadKey={selectedThread ? threadKey(selectedThread) : null}
              onSelectThread={setSelectedThread}
              refreshKey={refreshKey}
            />
            {selectedThread ? (
              <ThreadDetail
                thread={selectedThread}
                onBack={() => setSelectedThread(null)}
                onReply={selectedThread.manual_inbox_id == null ? handleReply : undefined}
                onOpenRequest={(requestId) => navigate(`/requests/${requestId}`)}
                onRead={handleThreadRead}
              />
            ) : (
              <EmptyState className="hidden xl:flex" />
            )}
          </>
        ) : (
          <UnmatchedInbox preselectId={wantedInboxId} />
        )}
      </div>

      {composerCtx && <Composer context={composerCtx} onClose={() => setComposerCtx(null)} onSent={handleSent} />}
    </div>
  );
}

function EmptyState({ className = '' }: { className?: string }) {
  return (
    <div className={cn('flex flex-1 flex-col items-center justify-center bg-ink-50/50 px-6 text-center', className)}>
      <div className="w-16 h-16 rounded-2xl bg-white border border-ink-200 flex items-center justify-center mb-4 shadow-sm">
        <Mail size={28} className="text-ink-300" />
      </div>
      <p className="text-sm font-medium text-ink-500">Выберите письмо, чтобы прочитать его</p>
    </div>
  );
}

function UnmatchedInbox({ preselectId }: { preselectId?: number | null }) {
  const [items, setItems] = useState<InboxMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(false);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<InboxMessage | null>(null);
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyNotice, setReplyNotice] = useState('');
  // Привязка письма к заявке. Автоматическое сопоставление работает по
  // заголовкам ответа и по «тема + адрес», поэтому новое письмо от поставщика
  // (не ответ на наше) в заявку не попадает — его привязывает человек.
  const [suggestions, setSuggestions] = useState<InboxSuggestion[]>([]);
  const [attaching, setAttaching] = useState(false);
  const [attachError, setAttachError] = useState('');
  const [linkedRequest, setLinkedRequest] = useState<ManualLinkRequestOption | null>(null);
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkQuery, setLinkQuery] = useState('');
  const [requestOptions, setRequestOptions] = useState<ManualLinkRequestOption[]>([]);
  const [requestOptionsLoading, setRequestOptionsLoading] = useState(false);
  const [requestOptionsError, setRequestOptionsError] = useState(false);
  const [requestRetryToken, setRequestRetryToken] = useState(0);
  const [selectedRequest, setSelectedRequest] = useState<ManualLinkRequestOption | null>(null);
  const [selectedSupplierId, setSelectedSupplierId] = useState<number | null>(null);
  const detailScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLoading(true);
    setListError(false);
    api
      .listInbox()
      .then((res) => {
        setItems(res.items);
        // Переход с дашборда/навигации — сразу открыть письмо, которое там
        // показывали, а не заставлять искать его в списке заново.
        if (preselectId != null) {
          const found = res.items.find((m) => m.id === preselectId);
          if (found) openMessage(found);
        }
      })
      .catch(() => setListError(true))
      .finally(() => setLoading(false));
  }, [preselectId]);

  useEffect(() => {
    if (!linkModalOpen) return undefined;
    const timer = window.setTimeout(() => {
      setRequestOptionsLoading(true);
      setRequestOptionsError(false);
      api.manualLinkRequests(linkQuery)
        .then((res) => setRequestOptions(res.items))
        .catch(() => setRequestOptionsError(true))
        .finally(() => setRequestOptionsLoading(false));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [linkModalOpen, linkQuery, requestRetryToken]);

  useEffect(() => {
    if (!linkModalOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLinkModalOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [linkModalOpen]);

  const visibleItems = search.trim()
    ? items.filter((m) => {
        const q = search.trim().toLowerCase();
        return m.from_email.toLowerCase().includes(q) || m.subject.toLowerCase().includes(q);
      })
    : items;

  const openMessage = (msg: InboxMessage) => {
    setSelected(msg);
    setReplyOpen(false);
    setReplyNotice('');
    setSuggestions([]);
    setAttachError('');
    setLinkedRequest(null);
    // Loading the conversation acknowledges the incoming message on the
    // server. Only update the list after that succeeds, so a failed read
    // request does not silently lose the unread marker.
    void api.inboxConversation(msg.id).then(() => {
      setItems((prev) => prev.map((item) => item.id === msg.id ? { ...item, unread: false } : item));
      setSelected((current) => current?.id === msg.id ? { ...current, unread: false } : current);
    }).catch(() => {});
    api.inboxSuggestions(msg.id).then((res) => setSuggestions(res.items)).catch(() => setSuggestions([]));
  };

  useEffect(() => {
    const resetScroll = () => detailScrollRef.current?.scrollTo({ top: 0, behavior: 'auto' });
    resetScroll();
    const frameId = window.requestAnimationFrame(resetScroll);
    const timeoutId = window.setTimeout(resetScroll, 120);
    return () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(timeoutId);
    };
  }, [selected?.id]);

  const openLinkDialog = (suggestion?: InboxSuggestion) => {
    if (!selected) return;
    setAttachError('');
    setLinkQuery('');
    setRequestOptionsLoading(true);
    setRequestOptionsError(false);
    setSelectedSupplierId(suggestion?.supplier_id ?? (linkedRequest ? selectedSupplierId : null));
    setSelectedRequest(suggestion ? {
      id: suggestion.request_id,
      name: suggestion.request_name,
      description: null,
      sender_name: '',
      company_name: '',
      status: 'unknown',
      supplier_names: [suggestion.supplier_name],
      supplier_emails: [suggestion.supplier_email],
    } : linkedRequest);
    setLinkModalOpen(true);
  };

  const confirmManualLink = async () => {
    if (!selected || !selectedRequest) return;
    setAttaching(true);
    setAttachError('');
    try {
      await api.manuallyLinkInboxMessage({
        inbox_message_id: selected.id,
        request_id: selectedRequest.id,
        supplier_id: selectedSupplierId,
        confirmed: true,
      });
      setLinkedRequest(selectedRequest);
      setItems((prev) => prev.filter((m) => m.id !== selected.id));
      setSearch('');
      setLinkModalOpen(false);
      window.dispatchEvent(new CustomEvent('supplydesk:unmatched-mail-changed', { detail: { delta: -1 } }));
    } catch (err) {
      setAttachError(err instanceof ApiError ? err.message : 'Не удалось привязать письмо к заявке.');
    } finally {
      setAttaching(false);
    }
  };

  const unlinkManualLink = async () => {
    if (!selected) return;
    setAttaching(true);
    setAttachError('');
    try {
      await api.unlinkManualInboxMessage(selected.id);
      setLinkedRequest(null);
      setItems((prev) => [selected, ...prev.filter((m) => m.id !== selected.id)]);
      setSearch('');
      window.dispatchEvent(new CustomEvent('supplydesk:unmatched-mail-changed', { detail: { delta: 1 } }));
      const res = await api.inboxSuggestions(selected.id).catch(() => ({ items: [] as InboxSuggestion[] }));
      setSuggestions(res.items);
    } catch (err) {
      setAttachError(err instanceof ApiError ? err.message : 'Не удалось отвязать письмо.');
    } finally {
      setAttaching(false);
    }
  };

  return (
    <>
      <div className={cn(
        'w-full shrink-0 border-r border-ink-200 bg-white flex-col xl:w-[360px] xl:flex',
        selected ? 'hidden' : 'flex',
      )}>
        <div className="px-3 pt-3 pb-2.5 border-b border-ink-100 shrink-0">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input
              aria-label="Поиск писем без привязки"
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
        ) : listError ? (
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <Mail size={32} className="mb-3 text-ink-300" />
            <p className="text-sm text-ink-500">Не удалось загрузить письма</p>
            <button type="button" onClick={() => window.location.reload()} className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-accent-700 hover:bg-accent-50">
              <RefreshCw size={14} /> Повторить
            </button>
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
              aria-label={`${msg.from_email}: ${msg.subject || '(без темы)'}.${msg.unread ? ' Непрочитанное письмо.' : ''}`}
              className={cn('w-full border-l-2 px-3 py-2.5 text-left transition-colors', selected?.id === msg.id ? 'bg-accent-50/50 border-accent-500' : 'border-transparent hover:bg-ink-50')}
            >
              <div className="flex items-center justify-between gap-2 mb-0.5">
                <span className={cn('flex min-w-0 items-center gap-1.5 truncate text-sm', msg.unread ? 'font-bold text-ink-900' : 'font-medium text-ink-700')}>
                  <span aria-hidden="true" className={cn('h-2 w-2 shrink-0 rounded-full', msg.unread ? 'bg-amber-500' : 'bg-transparent')} />
                  <span className="truncate">{msg.from_email}</span>
                </span>
                <span className="text-xs text-ink-500 shrink-0">{formatRelativeDate(msg.received_at)}</span>
              </div>
              <p className="text-sm truncate text-ink-600">{msg.subject}</p>
              {msg.unread && <p className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-amber-700">Новое письмо</p>}
            </button>
          ))
        )}
        </div>
      </div>

      {selected ? (
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-ink-50/50">
          <div className="flex shrink-0 items-center gap-3 border-b border-ink-200 bg-white px-4 py-3.5 sm:px-5">
            <button aria-label="Вернуться к списку писем" onClick={() => setSelected(null)} className="-ml-1.5 flex min-h-10 min-w-10 items-center justify-center rounded-lg p-1.5 text-ink-500 hover:bg-ink-100 hover:text-ink-900">
              <ArrowLeft size={18} />
            </button>
            <h2 className="min-w-0 flex-1 truncate text-base font-semibold text-ink-900">{selected.subject}</h2>
            <button
              onClick={() => setReplyOpen(true)}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-ink-50 px-3 py-1.5 text-sm font-medium text-ink-700 hover:bg-ink-100"
            >
              <Reply size={15} />
              Ответить
            </button>
          </div>

          {replyNotice && (
            <div role="status" className="shrink-0 border-b border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800 sm:px-5">
              {replyNotice}
            </div>
          )}

          {/* This is an external status panel, not part of the email body. The
              selection opens a dialog so an accidental click cannot reclassify
              an incoming message. */}
          {linkedRequest ? (
            <div role="status" className="shrink-0 border-b border-emerald-200 bg-emerald-50/90 px-4 py-3 sm:px-5">
              <div className="flex items-start gap-2">
                <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-700" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-emerald-900">Письмо привязано к заявке №{linkedRequest.id}</p>
                  <p className="mt-0.5 truncate text-xs text-emerald-800">{linkedRequest.name}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button type="button" disabled={attaching} onClick={() => openLinkDialog()} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-emerald-900 ring-1 ring-emerald-300 transition-colors hover:bg-emerald-100 disabled:opacity-50">
                      <LinkIcon size={13} /> Изменить
                    </button>
                    <button type="button" disabled={attaching} onClick={() => void unlinkManualLink()} className="inline-flex min-h-9 items-center rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-900 transition-colors hover:bg-emerald-100 disabled:opacity-50">
                      Отвязать
                    </button>
                  </div>
                  {attachError && <p role="alert" className="mt-2 text-xs text-rose-700">{attachError}</p>}
                </div>
              </div>
            </div>
          ) : (
            <div className="shrink-0 border-b border-amber-200/70 bg-amber-50/80 px-4 py-3 sm:px-5">
              <div className="flex items-center gap-2 text-xs font-semibold text-amber-800">
                <LinkIcon size={14} />Письмо не привязано к заявке
              </div>
              {suggestions.length > 0 ? (
                <>
                  <p className="mt-1 text-xs text-amber-700">Есть совпадения по отправителю. Выберите вариант, чтобы открыть привязку:</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {suggestions.slice(0, 6).map((sug) => (
                      <button
                        key={`${sug.request_id}:${sug.supplier_id}`}
                        disabled={attaching}
                        onClick={() => openLinkDialog(sug)}
                        title={`${sug.supplier_name} · ${sug.supplier_email}`}
                        className="inline-flex min-h-10 max-w-full items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-700 transition-colors hover:border-accent-400 hover:text-accent-700 disabled:opacity-50"
                      >
                        <span className="truncate">{sug.request_name}</span>
                        {sug.match === 'domain' && <span className="shrink-0 rounded bg-amber-100 px-1 py-px text-[10px] text-amber-800">тот же домен</span>}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <p className="mt-1 text-xs text-amber-700">Отправитель не совпал ни с одним поставщиком в заявках. Выберите заявку вручную:</p>
              )}
              <button type="button" disabled={attaching} onClick={() => openLinkDialog()} className="mt-2 inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 transition-colors hover:border-accent-400 hover:text-accent-700 disabled:opacity-50">
                <LinkIcon size={14} /> Привязать к заявке
              </button>
              {attachError && <p role="alert" className="mt-1.5 text-xs text-rose-600">{attachError}</p>}
            </div>
          )}
          <div ref={detailScrollRef} className="flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-[1180px] space-y-4 px-4 py-5 sm:px-6 lg:px-10 xl:px-12">
              <div className="rounded-2xl border border-ink-200 bg-white px-5 py-4 shadow-sm sm:px-6">
                <p className="text-2xs font-semibold uppercase tracking-wider text-ink-600">Входящее письмо</p>
                <div className="mt-2 flex min-w-0 items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink-900">{selected.from_email}</p>
                    <p className="mt-1 break-words text-xs text-ink-500">Кому: {selected.to_email}</p>
                  </div>
                  <time className="shrink-0 text-xs text-ink-500" dateTime={selected.received_at}>{formatFullDate(selected.received_at)}</time>
                </div>
              </div>

              <section aria-label="Содержание входящего письма" className="overflow-hidden rounded-2xl border border-ink-200 bg-white px-5 py-6 shadow-sm sm:px-8 sm:py-7">
                <EmailRenderer html={selected.body_html} text={selected.body_text} hasRemoteImages={selected.has_remote_images} />
              </section>

            </div>
          </div>
        </div>
      ) : (
        <EmptyState className="hidden xl:flex" />
      )}

      {replyOpen && selected && (
        <InboxReplyComposer
          message={selected}
          onClose={() => setReplyOpen(false)}
          onSent={() => {
            setReplyOpen(false);
            setReplyNotice(`Ответ на письмо ${selected.from_email} отправлен.`);
          }}
        />
      )}

      {linkModalOpen && selected && (
        <div
          className="fixed inset-0 z-[70] flex items-end justify-center bg-ink-950/35 p-0 sm:items-center sm:p-6"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setLinkModalOpen(false); }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="manual-link-title"
            className="max-h-[min(720px,92vh)] w-full overflow-y-auto rounded-t-2xl bg-white shadow-2xl sm:max-w-xl sm:rounded-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start gap-4 border-b border-ink-200 px-5 py-4 sm:px-6">
              <div className="min-w-0 flex-1">
                <h2 id="manual-link-title" className="text-lg font-semibold text-ink-900">Привязать письмо к заявке</h2>
                <p className="mt-1 text-sm leading-5 text-ink-600">Выберите заявку, к которой нужно отнести это письмо. Привязка будет сохранена вручную</p>
              </div>
              <button type="button" aria-label="Закрыть" onClick={() => setLinkModalOpen(false)} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-500 hover:bg-ink-100 hover:text-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4 px-5 py-5 sm:px-6">
              {!selectedRequest ? (
                <>
                  <div className="relative">
                    <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
                    <input
                      autoFocus
                      aria-label="Поиск заявок для привязки письма"
                      value={linkQuery}
                      onChange={(event) => setLinkQuery(event.target.value)}
                      placeholder="Номер, название, описание, заказчик или поставщик"
                      className="w-full rounded-lg border border-ink-200 bg-ink-50 py-2.5 pl-9 pr-3 text-sm text-ink-900 outline-none transition-colors placeholder:text-ink-400 focus:border-accent-400 focus:bg-white focus:ring-2 focus:ring-accent-100"
                    />
                  </div>
                  {requestOptionsLoading ? (
                    <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink-500"><Loader2 size={18} className="animate-spin" />Загружаем заявки…</div>
                  ) : requestOptionsError ? (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-5 text-center">
                      <p className="text-sm text-rose-800">Не удалось загрузить заявки</p>
                      <button type="button" onClick={() => setRequestRetryToken((value) => value + 1)} className="mt-3 inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-rose-800 ring-1 ring-rose-200 hover:bg-rose-100"><RefreshCw size={14} /> Повторить</button>
                    </div>
                  ) : requestOptions.length === 0 ? (
                    <div className="rounded-xl border border-ink-200 bg-ink-50 px-4 py-8 text-center text-sm text-ink-500">Заявки по этому запросу не найдены</div>
                  ) : (
                    <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                      {requestOptions.map((option) => {
                        const suggestion = suggestions.find((item) => item.request_id === option.id);
                        return (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => {
                              setSelectedRequest(option);
                              setSelectedSupplierId(suggestion?.supplier_id ?? null);
                            }}
                            className="w-full rounded-xl border border-ink-200 px-4 py-3 text-left transition-colors hover:border-accent-400 hover:bg-accent-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500"
                          >
                            <div className="flex items-start gap-3">
                              <span className="shrink-0 text-sm font-semibold text-accent-700">№{option.id}</span>
                              <span className="min-w-0 flex-1">
                                <span className="block truncate text-sm font-semibold text-ink-900">{option.name}</span>
                                <span className="mt-1 block text-xs text-ink-500">Статус: {requestStatusLabel(option.status)}</span>
                                {option.supplier_names.length > 0 && <span className="mt-1 block truncate text-xs text-ink-600">Поставщики: {option.supplier_names.join(', ')}</span>}
                              </span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </>
              ) : (
                <div className="space-y-4">
                  <div className="rounded-xl border border-accent-200 bg-accent-50/50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-accent-700">Выбрана заявка</p>
                    <p className="mt-1 text-sm font-semibold text-ink-900">№{selectedRequest.id} · {selectedRequest.name}</p>
                    {selectedSupplierId != null ? (
                      <p className="mt-2 text-xs text-ink-600">Поставщик: {selectedRequest.supplier_names[0] || 'совпадение по отправителю'}</p>
                    ) : (
                      <p className="mt-2 text-xs text-ink-600">Поставщик не выбран. Связь с поставщиком не изменяется.</p>
                    )}
                  </div>
                  <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-center">
                    <p className="text-sm font-semibold text-amber-950">Привязать это письмо к заявке №{selectedRequest.id}?</p>
                    <p className="mt-1 text-xs leading-5 text-amber-900/80">Действие сохраняется вручную и не изменяет текст, отправителя или историю письма.</p>
                  </div>
                  {attachError && <p role="alert" className="text-sm text-rose-700">{attachError}</p>}
                  <div className="flex flex-wrap justify-end gap-2">
                    <button type="button" disabled={attaching} onClick={() => { setSelectedRequest(null); setSelectedSupplierId(null); setAttachError(''); }} className="min-h-10 rounded-lg px-3 py-1.5 text-sm font-semibold text-ink-600 hover:bg-ink-100 disabled:opacity-50">Изменить выбор</button>
                    <button type="button" disabled={attaching} onClick={() => setLinkModalOpen(false)} className="min-h-10 rounded-lg px-3 py-1.5 text-sm font-semibold text-ink-700 hover:bg-ink-100 disabled:opacity-50">Отмена</button>
                    <button type="button" disabled={attaching} onClick={() => void confirmManualLink()} className="inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-accent-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-700 disabled:opacity-50">
                      {attaching ? <Loader2 size={15} className="animate-spin" /> : <LinkIcon size={15} />}
                      Подтвердить привязку
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function requestStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: 'черновик',
    searching: 'поиск поставщиков',
    updating: 'обновление',
    completed: 'готова',
    error: 'ошибка',
  };
  return labels[status] ?? status;
}
