import { useEffect, useState } from 'react';
import { ArrowLeft, ChevronDown, ChevronUp, ExternalLink, Loader2, Reply } from 'lucide-react';
import { api } from '@/lib/api';
import { cn, formatFullDate, getAvatarColor, getInitials } from '@/lib/utils';
import { EmailRenderer } from '@/components/mail/EmailRenderer';
import type { MailMessage, ThreadSummary } from '@/lib/types';

const OUTBOUND_STATUS_LABELS: Record<string, string> = {
  queued: 'в очереди',
  sending: 'отправляется',
  sent: 'отправлено',
  failed: 'ошибка отправки',
};

interface ThreadDetailProps {
  thread: ThreadSummary;
  onBack: () => void;
  onReply: (thread: ThreadSummary, lastMessage: MailMessage | null) => void;
  onOpenRequest?: (requestId: number) => void;
}

export function ThreadDetail({ thread, onBack, onReply, onOpenRequest }: ThreadDetailProps) {
  const [messages, setMessages] = useState<MailMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    api
      .threadMessages(thread.request_id, thread.supplier_id)
      .then((res) => {
        if (cancelled) return;
        setMessages(res.items);
        if (res.items.length > 1) setCollapsed(new Set(res.items.slice(0, -1).map((m) => m.id)));
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [thread.request_id, thread.supplier_id]);

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
      </div>
    );
  }

  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      <div className="px-5 py-3.5 border-b border-ink-100 shrink-0">
        <div className="flex items-center gap-3 mb-2">
          <button onClick={onBack} className="p-1.5 -ml-1.5 text-ink-500 hover:text-ink-900 hover:bg-ink-100 rounded-lg transition-colors">
            <ArrowLeft size={18} />
          </button>
          <h2 className="text-base font-semibold text-ink-900 truncate flex-1">{thread.subject}</h2>
          <button
            onClick={() => onReply(thread, lastMessage)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-ink-700 bg-ink-50 hover:bg-ink-100 rounded-lg transition-colors"
          >
            <Reply size={15} />
            Ответить
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-5 py-4 space-y-3">
          <div className="bg-gradient-to-b from-ink-50 to-white border border-ink-200 rounded-xl p-3.5 mb-2">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-semibold text-ink-400 uppercase tracking-wider mb-1">Заявка</p>
                <p className="text-sm font-medium text-ink-900">{thread.request_name}</p>
                <p className="text-sm text-ink-500 mt-0.5">{thread.supplier_name}</p>
              </div>
              {onOpenRequest && (
                <button
                  onClick={() => onOpenRequest(thread.request_id)}
                  className="inline-flex items-center gap-1 text-sm text-accent-600 hover:text-accent-700 font-medium shrink-0"
                >
                  Открыть заявку
                  <ExternalLink size={13} />
                </button>
              )}
            </div>
          </div>

          {messages.length === 0 && <p className="text-sm text-ink-400 py-8 text-center">В этой переписке пока нет сообщений</p>}

          {messages.map((msg, idx) => {
            const isCollapsed = collapsed.has(msg.id);
            const isLast = idx === messages.length - 1;
            const fromName = msg.direction === 'outbound' ? 'Вы' : thread.supplier_name;
            const avatarColor = getAvatarColor(fromName);
            const initials = getInitials(fromName);

            return (
              <div key={msg.id} className={cn('border border-ink-200 rounded-xl overflow-hidden transition-all duration-200', isLast && 'shadow-sm')}>
                <button onClick={() => toggleCollapse(msg.id)} className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-ink-50 transition-colors">
                  <div
                    className={cn(
                      'w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold shrink-0',
                      msg.direction === 'outbound' ? 'bg-ink-200 text-ink-600' : avatarColor
                    )}
                  >
                    {initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-ink-900 truncate">{fromName}</span>
                      {msg.direction === 'outbound' && (
                        <span className={cn('text-xs', msg.status === 'failed' ? 'text-rose-500' : 'text-ink-400')}>
                          · {OUTBOUND_STATUS_LABELS[msg.status] ?? msg.status}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-ink-400 truncate">
                      {isCollapsed
                        ? (msg.body_text || '').replace(/\s+/g, ' ').trim().slice(0, 80) || (msg.direction === 'outbound' ? msg.to_email : msg.from_email)
                        : (msg.direction === 'outbound' ? msg.to_email : msg.from_email)}
                    </p>
                  </div>
                  <span className="text-xs text-ink-400 shrink-0">{formatFullDate(msg.sent_at || msg.created_at)}</span>
                  {messages.length > 1 && <div className="shrink-0 text-ink-400">{isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}</div>}
                </button>

                {!isCollapsed && (
                  <div className="px-4 pb-4">
                    <div className="border-t border-ink-100 pt-3">
                      <EmailRenderer html={msg.body_html} text={msg.body_text} />
                      {msg.error && <p className="mt-2 text-xs text-rose-600">Ошибка отправки: {msg.error}</p>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {messages.length > 0 && (
            <button
              onClick={() => onReply(thread, lastMessage)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium text-white bg-accent-600 hover:bg-accent-700 rounded-xl transition-colors"
            >
              <Reply size={15} />Ответить
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
