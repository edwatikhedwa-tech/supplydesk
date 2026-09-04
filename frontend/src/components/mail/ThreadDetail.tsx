import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, CheckCircle2, ChevronDown, ChevronUp, ExternalLink, Link as LinkIcon, Loader2, RefreshCw, Reply, Send, ShieldCheck } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, displayCorrespondenceSupplierName, formatFullDate, getAvatarColor, getInitials } from '@/lib/utils';
import { EmailRenderer } from '@/components/mail/EmailRenderer';
import { ThreadMetadataControls } from '@/components/mail/ThreadMetadataControls';
import { getThreadDisplayStatus } from '@/components/mail/threadStatus';
import { Button } from '@/components/ui/button';
import { StatusBadge, type StatusBadgeTone } from '@/components/ui/StatusBadge';
import type { InboxConversation, MailMessage, ThreadSummary } from '@/lib/types';

const OUTBOUND_STATUS_LABELS: Record<string, string> = {
  queued: 'в очереди',
  sending: 'отправляется',
  sent: 'отправлено',
  failed: 'ошибка отправки',
  delivery_unknown: 'отправка не подтверждена',
  bounced: 'письмо возвращено',
};

function outboundStatusTone(status: string): StatusBadgeTone {
  if (status === 'sent') return 'neutral';
  if (status === 'delivery_unknown') return 'warning';
  if (status === 'failed' || status === 'bounced') return 'danger';
  return 'warning';
}

interface ThreadDetailProps {
  thread: ThreadSummary;
  onBack: () => void;
  onReply?: (thread: ThreadSummary, lastMessage: MailMessage | null) => void;
  onOpenRequest?: (requestId: number) => void;
  /** Отвязать вручную сопоставленное письмо и вернуть его во входящие без привязки. */
  onUnlinkManual?: (inboxMessageId: number) => Promise<void>;
  /** Вызывается после загрузки писем: сервер к этому моменту уже пометил
   *  входящие прочитанными, и список тредов надо перезапросить. */
  onRead?: () => void;
  /** Сохраняет личные флаг важности и приоритет с optimistic rollback. */
  onMetadataChange?: (thread: ThreadSummary, patch: { important?: boolean; priority?: 1 | 2 | 3 | null }) => Promise<void>;
}

function mapInboxConversation(conversation: InboxConversation): MailMessage[] {
  const original: MailMessage = {
    id: conversation.id,
    direction: 'inbound',
    from_email: conversation.from_email,
    to_email: conversation.to_email,
    subject: conversation.subject,
    body_text: conversation.body_text,
    body_html: conversation.body_html,
    status: 'received',
    error: null,
    message_id: conversation.message_id ?? null,
    in_reply_to: null,
    references_header: conversation.references_header ?? null,
    created_at: conversation.received_at,
    sent_at: conversation.received_at,
    has_remote_images: conversation.has_remote_images,
  };
  const replies: MailMessage[] = conversation.replies.map((reply) => ({
    id: -reply.id,
    direction: 'outbound',
    from_email: reply.from_email,
    to_email: reply.to_email,
    subject: reply.subject,
    body_text: reply.body_text,
    body_html: reply.body_html,
    status: reply.status,
    error: reply.error,
    message_id: reply.message_id,
    in_reply_to: reply.in_reply_to,
    references_header: reply.references_header,
    created_at: reply.created_at,
    sent_at: reply.sent_at,
    has_remote_images: reply.has_remote_images,
  }));
  return [original, ...replies];
}

export function ThreadDetail({ thread, onBack, onReply, onOpenRequest, onUnlinkManual, onRead, onMetadataChange }: ThreadDetailProps) {
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionBusy, setActionBusy] = useState<number | null>(null);
  const [confirmResend, setConfirmResend] = useState<number | null>(null);
  const [unlinkBusy, setUnlinkBusy] = useState(false);
  const [unlinkError, setUnlinkError] = useState('');

  const unlinkManual = async () => {
    if (thread.manual_inbox_id == null || !onUnlinkManual) return;
    setUnlinkBusy(true);
    setUnlinkError('');
    try {
      await onUnlinkManual(thread.manual_inbox_id);
    } catch (error) {
      setUnlinkError(error instanceof Error ? error.message : 'Не удалось отвязать письмо.');
    } finally {
      setUnlinkBusy(false);
    }
  };

  const loadMessages = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      if (thread.manual_inbox_id != null) {
        const conversation = await api.inboxConversation(thread.manual_inbox_id);
        setMessages(mapInboxConversation(conversation));
        setCollapsed(new Set());
        onRead?.();
        return;
      }
      const res = await api.threadMessages(thread.request_id, thread.supplier_id);
      setMessages(res.items);
      if (res.items.length > 1) setCollapsed(new Set(res.items.slice(0, -1).map((m) => m.id)));
      if (res.items.some((m) => m.direction === 'inbound')) onRead?.();
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [thread.manual_inbox_id, thread.request_id, thread.supplier_id, onRead]);

  useEffect(() => {
    void loadMessages();
  }, [loadMessages]);

  const verify = async (messageId: number) => {
    setActionBusy(messageId);
    setActionError('');
    setActionMessage('');
    try {
      const result = await api.verifyDelivery(messageId);
      setActionMessage(result.outcome === 'found' ? 'Письмо найдено в «Отправленных». Факт отправки подтверждён.' : 'Подтверждение пока не получено. Письмо не возвращено в очередь.');
      await loadMessages();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось проверить отправку.');
    } finally {
      setActionBusy(null);
    }
  };

  const resend = async (messageId: number, confirmed: boolean) => {
    setActionBusy(messageId);
    setActionError('');
    setActionMessage('');
    try {
      const result = await api.resendDelivery(messageId, confirmed);
      if (result.requires_confirmation) {
        setConfirmResend(messageId);
        setActionMessage(result.warning || 'Оригинал не подтверждён. Повтор может создать дубликат.');
      } else if (result.resent) {
        setConfirmResend(null);
        setActionMessage('Создано новое письмо с новым идентификатором.');
        await loadMessages();
      } else if (result.outcome === 'found') {
        setConfirmResend(null);
        setActionMessage('Оригинал найден в «Отправленных». Повтор не создан.');
        await loadMessages();
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось подготовить повторную отправку.');
    } finally {
      setActionBusy(null);
    }
  };

  const resolve = async (messageId: number) => {
    setActionBusy(messageId);
    setActionError('');
    setActionMessage('');
    try {
      await api.resolveDelivery(messageId);
      setActionMessage('Вопрос закрыт. Факт доставки по-прежнему отображается как «не подтверждён».');
      await loadMessages();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Не удалось закрыть вопрос.');
    } finally {
      setActionBusy(null);
    }
  };

  const toggleCollapse = (id: number) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={24} className="text-ink-300 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
        <p className="text-sm text-ink-500">Не удалось загрузить переписку</p>
        <Button size="sm" variant="secondary" onClick={() => void loadMessages()} className="mt-3">
          <RefreshCw size={14} /> Повторить
        </Button>
      </div>
    );
  }

  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  const lastMessagePending = lastMessage?.direction === 'outbound' && ['queued', 'sending'].includes(lastMessage.status);
  const canReply = Boolean(onReply && !lastMessagePending);
  const supplierLabel = displayCorrespondenceSupplierName(thread.supplier_name) || 'Поставщик не определён';
  const threadStatus = getThreadDisplayStatus(thread);

  return (
    <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-ink-50/60">
      <div className="shrink-0 border-b border-ink-200 bg-white px-4 py-3.5 sm:px-6">
        <div className="flex items-start gap-3">
          <button aria-label="Вернуться к списку переписок" onClick={onBack} className="-ml-1.5 flex min-h-10 min-w-10 items-center justify-center rounded-lg p-1.5 text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900">
            <ArrowLeft size={18} />
          </button>
          <div className="min-w-0 flex-1">
            <p className="text-2xs font-bold uppercase tracking-[0.16em] text-accent-700">Переписка</p>
            <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1">
              <h2 className="truncate text-lg font-bold tracking-tight text-ink-900" title={thread.supplier_name || undefined}>{supplierLabel}</h2>
              <StatusBadge label={threadStatus.label} tone={threadStatus.tone} title={threadStatus.title} dot />
            </div>
            <p className="mt-1 truncate text-sm text-ink-600">{thread.subject || 'Без темы'}</p>
            <div className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-ink-500">
              <span className="inline-flex items-center gap-1.5 font-semibold text-ink-700">
                <LinkIcon size={13} aria-hidden="true" />
                <span className="sr-only">Связано с заявкой:</span>
                <span className="max-w-[30rem] truncate" title={thread.request_name}>{thread.request_name}</span>
              </span>
              <span aria-hidden="true" className="text-ink-300">·</span>
              <span>{thread.supplier_email || 'Адрес поставщика не указан'}</span>
              <span aria-hidden="true" className="text-ink-300">·</span>
              <span>заявка №{thread.request_id}</span>
              {onOpenRequest && (
                <Button
                  variant="link"
                  size="sm"
                  onClick={() => onOpenRequest(thread.request_id)}
                  className="min-h-8 px-1 text-xs"
                >
                  Открыть заявку
                  <ExternalLink size={13} />
                </Button>
              )}
              {thread.manual_inbox_id != null && <span className="font-medium text-accent-600">Связано вручную</span>}
              {thread.manual_inbox_id != null && onUnlinkManual && (
                <button
                  type="button"
                  onClick={() => void unlinkManual()}
                  disabled={unlinkBusy}
                  aria-busy={unlinkBusy}
                  className="min-h-8 rounded-lg px-2 text-xs font-semibold text-ink-600 hover:bg-ink-50 hover:text-ink-900 disabled:cursor-wait disabled:opacity-60"
                >
                  {unlinkBusy ? 'Отвязываем…' : 'Отвязать'}
                </button>
              )}
            </div>
            {unlinkError && <p role="alert" className="mt-1 text-xs text-rose-700">{unlinkError}</p>}
          </div>
          {onMetadataChange && thread.manual_inbox_id == null && (
            <ThreadMetadataControls important={thread.is_important} priority={thread.priority} onChange={(patch) => onMetadataChange(thread, patch)} />
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-8 lg:px-10">

          {messages.length === 0 && <p className="text-sm text-ink-400 py-8 text-center">В этой переписке пока нет сообщений</p>}

          {messages.map((msg) => {
            const isCollapsed = collapsed.has(msg.id);
            const isOutbound = msg.direction === 'outbound';
            const fromName = isOutbound ? 'Вы' : (thread.supplier_name || msg.from_email);
            const avatarColor = getAvatarColor(fromName);
            const initials = getInitials(fromName);
            const messagePanelId = `message-body-${msg.id}`;
            const collapsedPreview = (msg.body_text || '').replace(/\s+/g, ' ').trim().slice(0, 80);

            return (
              <article key={msg.id} className={cn('group/message relative flex pb-8 last:pb-0', isOutbound ? 'justify-end' : 'justify-start')}>
                <div className={cn('min-w-0 w-full', isOutbound ? 'max-w-3xl' : 'max-w-4xl')}>
                  <button
                    type="button"
                    aria-expanded={!isCollapsed}
                    aria-controls={messagePanelId}
                    aria-label={`${isCollapsed ? 'Развернуть' : 'Свернуть'} сообщение от ${fromName}`}
                    onClick={() => toggleCollapse(msg.id)}
                    className={cn(
                      'flex w-full items-center gap-2 px-1.5 py-1 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-400 focus-visible:ring-offset-2',
                      isOutbound ? 'justify-end text-right' : 'justify-start',
                    )}
                  >
                    {!isOutbound && (
                      <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-2xs font-semibold', avatarColor)} aria-hidden="true">
                        {initials}
                      </span>
                    )}
                    <span className={cn('min-w-0', isOutbound ? 'order-1' : '')}>
                      <span className={cn('flex items-center gap-2', isOutbound ? 'justify-end' : '')}>
                        <span className="truncate text-sm font-semibold text-ink-900">{fromName}</span>
                        <span className="shrink-0 text-2xs font-semibold uppercase tracking-[0.12em] text-ink-500">{isOutbound ? 'Исходящее' : 'Входящее'}</span>
                        {isOutbound && (
                          <StatusBadge label={OUTBOUND_STATUS_LABELS[msg.status] ?? msg.status} tone={outboundStatusTone(msg.status)} />
                        )}
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-ink-500">
                        {isCollapsed ? collapsedPreview || (isOutbound ? msg.to_email : msg.from_email) : (isOutbound ? msg.to_email : msg.from_email)}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs text-ink-500">{formatFullDate(msg.sent_at || msg.created_at)}</span>
                    {messages.length > 1 && (
                      <span className="shrink-0 text-ink-400 transition-colors group-hover/message:text-ink-700 group-focus-within/message:text-ink-700" aria-hidden="true">
                        {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                      </span>
                    )}
                  </button>

                  {!isCollapsed && (
                    <div
                      id={messagePanelId}
                      className={cn(
                        'mt-2 min-w-0 overflow-hidden px-4 pb-5 pt-4 shadow-soft sm:px-5',
                        isOutbound
                          ? 'rounded-2xl rounded-tr-md bg-accent-50 ring-1 ring-accent-100'
                          : 'rounded-2xl rounded-tl-md bg-white/80 ring-1 ring-ink-200/70',
                      )}
                    >
                      <EmailRenderer html={msg.body_html} text={msg.body_text} hasRemoteImages={msg.has_remote_images} />
                      {msg.error && <p className="mt-2 text-xs text-rose-700">Ошибка отправки: {msg.error}</p>}
                      {isOutbound && msg.status === 'delivery_unknown' && (
                        <div className="mt-4 rounded-xl border border-orange-200 bg-orange-50/80 p-3.5" role="alert">
                          <div className="flex items-start gap-2.5">
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-orange-700" />
                            <div className="min-w-0 flex-1">
                              <p className="text-sm font-semibold text-orange-950">Отправка не подтверждена</p>
                              <p className="mt-1 text-xs leading-relaxed text-orange-900/80">Система не знает, принял ли сервер это письмо. Оно не будет отправлено повторно автоматически.</p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() => verify(msg.id)}
                                  disabled={actionBusy === msg.id}
                                  className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-orange-900 ring-1 ring-orange-300 transition-colors hover:bg-orange-100 disabled:opacity-60"
                                >
                                  {actionBusy === msg.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                                  Проверить ещё раз
                                </button>
                                {!msg.delivery_resolved && confirmResend !== msg.id && (
                                  <button
                                    type="button"
                                    onClick={() => resend(msg.id, false)}
                                    disabled={actionBusy === msg.id}
                                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-orange-700 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-orange-800 disabled:opacity-60"
                                  >
                                    <Send className="h-3.5 w-3.5" />
                                    Отправить повторно
                                  </button>
                                )}
                                {!msg.delivery_resolved && confirmResend === msg.id && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => resend(msg.id, true)}
                                      disabled={actionBusy === msg.id}
                                      className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-orange-700 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-orange-800 disabled:opacity-60"
                                    >
                                      <Send className="h-3.5 w-3.5" />
                                      Подтвердить повтор
                                    </button>
                                    <button type="button" onClick={() => setConfirmResend(null)} className="min-h-9 rounded-lg px-3 py-1.5 text-xs font-semibold text-orange-900 hover:bg-orange-100">Отмена</button>
                                  </>
                                )}
                                {!msg.delivery_resolved && (
                                  <button
                                    type="button"
                                    onClick={() => resolve(msg.id)}
                                    disabled={actionBusy === msg.id}
                                    className="inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-orange-900 hover:bg-orange-100 disabled:opacity-60"
                                  >
                                    <ShieldCheck className="h-3.5 w-3.5" />
                                    Я разобрался, вопрос закрыт
                                  </button>
                                )}
                              </div>
                              {msg.delivery_resolved && <p className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-orange-900"><CheckCircle2 className="h-3.5 w-3.5" />Вопрос закрыт вручную; факт доставки не изменён.</p>}
                              {actionMessage && <p className="mt-2 text-xs font-medium text-orange-900">{actionMessage}</p>}
                              {actionError && <p className="mt-2 text-xs font-medium text-rose-700">{actionError}</p>}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </article>
            );
          })}

        </div>
      </div>
      {canReply ? (
        <div className="shrink-0 border-t border-ink-200 bg-white/95 px-4 py-3.5 backdrop-blur-sm sm:px-8">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-2xs font-bold uppercase tracking-[0.16em] text-accent-700">Следующий шаг</p>
              <p className="mt-0.5 truncate text-xs text-ink-500">Продолжите разговор с поставщиком</p>
            </div>
            <Button
              variant="primary"
              size="md"
              aria-label="Ответить"
              title="Ответить поставщику"
              onClick={() => onReply?.(thread, lastMessage)}
              className="shrink-0"
            >
              <Reply size={16} />
              Ответить поставщику
            </Button>
          </div>
        </div>
      ) : lastMessagePending ? (
        <div className="flex shrink-0 items-center justify-end border-t border-ink-200 bg-white px-4 py-3.5 sm:px-8">
          <StatusBadge label="Письмо отправляется" tone="warning" title="Ответ станет доступен после завершения текущей отправки" dot />
        </div>
      ) : null}
    </div>
  );
}
