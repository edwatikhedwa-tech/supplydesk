import { LifeBuoy, Paperclip, SendHorizontal } from 'lucide-react';
import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ApiError, api } from '../lib/api';
import type { MailAttachment, SupportCategory, SupportConversation, SupportConversationSummary } from '../lib/types';

const QUICK_ACTIONS: Array<{ label: string; category: SupportCategory }> = [
  { label: 'Сообщить об ошибке', category: 'bug' },
  { label: 'Задать технический вопрос', category: 'technical' },
  { label: 'Проблема с заявкой', category: 'request' },
  { label: 'Предложить улучшение', category: 'improvement' },
];

const STATUS_LABEL: Record<SupportConversation['status'], string> = {
  received: 'Получено',
  in_progress: 'В работе',
  waiting_user: 'Ждём вашего ответа',
  resolved: 'Решено',
};

const ALLOWED_FILES = new Set([
  'application/pdf', 'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain', 'image/jpeg', 'image/png', 'image/webp',
]);

function currentSection(pathname: string): string {
  if (pathname === '/') return 'dashboard';
  return pathname.split('/').filter(Boolean)[0] || 'dashboard';
}

function linkedRequestId(pathname: string): number | null {
  const match = pathname.match(/^\/requests\/(\d+)(?:\/|$)/);
  return match ? Number(match[1]) : null;
}

function readAttachment(file: File): Promise<MailAttachment> {
  return new Promise((resolve, reject) => {
    if (!ALLOWED_FILES.has(file.type)) {
      reject(new Error('Поддерживаются PDF, DOC, DOCX, TXT и изображения JPG, PNG, WEBP.'));
      return;
    }
    if (file.size === 0 || file.size > 10 * 1024 * 1024) {
      reject(new Error('Размер вложения не должен превышать 10 МБ.'));
      return;
    }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Не удалось прочитать вложение.'));
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : '';
      const base64 = result.split(',', 2)[1];
      if (!base64) {
        reject(new Error('Не удалось прочитать вложение.'));
        return;
      }
      resolve({ filename: file.name, mime_type: file.type, size: file.size, content_base64: base64 });
    };
    reader.readAsDataURL(file);
  });
}

function ticketLabel(item: SupportConversationSummary | SupportConversation): string {
  return `#${item.id} · ${STATUS_LABEL[item.status]}`;
}

type SupportChatProps = {
  compact?: boolean;
};

export function SupportChat({ compact = false }: SupportChatProps) {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [conversations, setConversations] = useState<SupportConversationSummary[]>([]);
  const [conversation, setConversation] = useState<SupportConversation | null>(null);
  const [text, setText] = useState('');
  const [category, setCategory] = useState<SupportCategory>('general');
  const [attachment, setAttachment] = useState<MailAttachment | undefined>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError('');
    api.listSupportConversations()
      .then((result) => setConversations(result.items))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Не удалось открыть обращения.'))
      .finally(() => setLoading(false));
  }, [open]);

  const startNew = () => {
    setConversation(null);
    setHistoryOpen(false);
    setText('');
    setAttachment(undefined);
    setCategory('general');
    setError('');
    window.setTimeout(() => composer.current?.focus(), 0);
  };

  const chooseConversation = async (id: number) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.getSupportConversation(id);
      setConversation(result.conversation);
      setHistoryOpen(false);
      setText('');
      setAttachment(undefined);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось открыть обращение.');
    } finally {
      setLoading(false);
    }
  };

  const send = async () => {
    const message = text.trim();
    if ((!message && !attachment) || sending) return;
    setSending(true);
    setError('');
    try {
      let result: SupportConversation;
      if (conversation) {
        result = (await api.sendSupportMessage(conversation.id, { text: message, attachment })).conversation;
      } else {
        result = (await api.createSupportConversation({
          text: message,
          category,
          linked_request_id: linkedRequestId(location.pathname),
          current_url: `${window.location.origin}${window.location.pathname}${window.location.hash}`,
          current_section: currentSection(location.pathname),
          app_version: import.meta.env.VITE_APP_VERSION || 'local',
          attachment,
        })).conversation;
      }
      setConversation(result);
      setConversations((items) => {
        const summary: SupportConversationSummary = {
          id: result.id, linked_request_id: result.linked_request_id, request_name: result.request_name,
          category: result.category, status: result.status, current_section: result.current_section,
          created_at: result.created_at, updated_at: result.updated_at, last_message: message,
        };
        return [summary, ...items.filter((item) => item.id !== result.id)];
      });
      setText('');
      setAttachment(undefined);
    } catch (cause) {
      const messageText = cause instanceof ApiError || cause instanceof Error ? cause.message : 'Не удалось отправить сообщение.';
      setError(messageText);
    } finally {
      setSending(false);
      composer.current?.focus();
    }
  };

  const quickStart = (action: typeof QUICK_ACTIONS[number]) => {
    setCategory(action.category);
    setText(`${action.label}. `);
    composer.current?.focus();
  };

  const onAttachment = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0];
    event.target.value = '';
    if (!selected) return;
    try {
      setAttachment(await readAttachment(selected));
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось добавить вложение.');
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={clsx(
          'flex h-9 w-full items-center gap-2.5 rounded-md border border-transparent px-2.5 text-[12px] font-medium text-rail-text transition-colors hover:bg-rail-hover hover:text-rail-text-active focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-border',
          compact && 'justify-center px-0',
        )}
        aria-label="Открыть техническую поддержку"
      >
        <LifeBuoy size={16} strokeWidth={1.75} className="shrink-0" />
        {!compact && <span>Поддержка</span>}
      </button>
      {open && (
        <section
          className="fixed bottom-4 right-4 z-50 flex h-[min(660px,calc(100dvh-32px))] w-[min(420px,calc(100vw-32px))] flex-col overflow-hidden rounded-[26px] border border-[#d9d9dd] bg-[#fffefe] text-[#1c1c20] shadow-[0_18px_55px_rgba(31,31,36,0.16)]"
          role="dialog"
          aria-modal="true"
          aria-label="Техническая поддержка SupplyDesk"
        >
          <header className="flex h-14 shrink-0 items-center border-b border-[#e7e7ea] px-5">
            <p className="text-[10px] font-semibold tracking-[0.11em] text-[#4b4b52]">SUPPLYDESK · SUPPORT</p>
            <div className="ml-auto flex items-center gap-3 text-[10px] font-semibold tracking-[0.1em] text-[#55555c]">
              <button type="button" onClick={startNew} className="hover:text-[#17171b] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]">NEW</button>
              <button type="button" onClick={() => setOpen(false)} className="text-[17px] font-normal leading-none hover:text-[#17171b] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]" aria-label="Закрыть поддержку">×</button>
            </div>
          </header>

          {conversation ? (
            <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-4 pt-3">
              <div className="mb-5 flex items-center justify-between gap-3 text-[10px] font-medium tracking-[0.03em] text-[#73737a]">
                <span>{ticketLabel(conversation)}</span>
                {conversation.request_name && <span className="truncate" title={conversation.request_name}>Заявка: {conversation.request_name}</span>}
              </div>
              <div className="flex flex-col gap-5">
                {conversation.messages.map((message) => (
                  <article key={message.id} className={message.sender_type === 'user' ? 'ml-8 text-right' : 'mr-8'}>
                    <p className="mb-1 text-[9px] font-semibold tracking-[0.12em] text-[#76767d]">{message.sender_type === 'support' ? 'SUPPORT' : 'YOU'}</p>
                    {message.text && <p className="whitespace-pre-wrap text-[13px] leading-5 text-[#2c2c31]">{message.text}</p>}
                    {message.attachment_url && (
                      <a href={message.attachment_url} className="mt-1 inline-block text-[11px] text-[#5d5d66] underline underline-offset-2 hover:text-[#222228]">
                        {message.attachment_filename}
                      </a>
                    )}
                  </article>
                ))}
              </div>
            </div>
          ) : historyOpen ? (
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
              <p className="mb-4 text-[10px] font-semibold tracking-[0.11em] text-[#76767d]">ПРЕДЫДУЩИЕ ОБРАЩЕНИЯ</p>
              {loading ? <p className="text-[13px] text-[#707078]">Загружаем…</p> : conversations.length === 0 ? <p className="text-[13px] text-[#707078]">Предыдущих обращений нет.</p> : (
                <div className="flex flex-col gap-1">
                  {conversations.map((item) => (
                    <button key={item.id} type="button" onClick={() => void chooseConversation(item.id)} className="rounded-lg px-2 py-2 text-left hover:bg-[#f4f4f5] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]">
                      <span className="block text-[11px] font-medium text-[#3f3f46]">{ticketLabel(item)}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-[#777780]">{item.last_message || 'Вложение'}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col justify-end px-7 pb-4 pt-10">
              <div className="max-w-[285px]">
                <p className="mb-3 text-[10px] font-semibold tracking-[0.13em] text-[#6b6b73]">SUPPORT</p>
                <h2 className="text-[27px] font-semibold leading-[1.04] tracking-[-0.045em] text-[#1d1d21]">Чем можем помочь?</h2>
                <p className="mt-3 text-[13px] leading-5 text-[#76767d]">Опишите проблему — мы разберёмся.</p>
                <p className="mb-2 mt-7 text-[10px] font-semibold tracking-[0.12em] text-[#6b6b73]">НАЧАТЬ С</p>
                <div className="flex flex-col items-start gap-0.5">
                  {QUICK_ACTIONS.map((action) => (
                    <button key={action.category} type="button" onClick={() => quickStart(action)} className="py-1 text-left text-[13px] text-[#39393f] hover:text-[#000] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]">
                      &gt; {action.label}
                    </button>
                  ))}
                </div>
                <Link
                  to="/help"
                  onClick={() => setOpen(false)}
                  className="mt-5 inline-flex text-[11px] font-medium text-[#777780] underline decoration-[#c7c7cd] underline-offset-4 transition-colors hover:text-[#17171b] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6053d9] focus-visible:ring-offset-2"
                >
                  Открыть справку по функциям
                </Link>
                {conversations.length > 0 && <button type="button" onClick={() => setHistoryOpen(true)} className="mt-3 block text-[11px] text-[#777780] underline underline-offset-2 hover:text-[#2d2d32] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]">Предыдущие обращения</button>}
              </div>
            </div>
          )}

          <div className="shrink-0 px-4 pb-4">
            {error && <p role="alert" className="mb-2 px-1 text-[11px] text-[#a23b32]">{error}</p>}
            {attachment && <div className="mb-1.5 flex items-center justify-between px-1 text-[11px] text-[#64646c]"><span className="truncate">{attachment.filename}</span><button type="button" onClick={() => setAttachment(undefined)} className="ml-2 underline underline-offset-2 hover:text-[#242429]">Убрать</button></div>}
            <div className="relative rounded-[16px] border border-[#d9d9de] bg-[#fbfbfc] px-10 py-3">
              <textarea
                ref={composer}
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    void send();
                  }
                }}
                rows={2}
                placeholder="Опишите проблему..."
                className="block max-h-28 min-h-[42px] w-full resize-none bg-transparent text-[13px] leading-5 text-[#232328] outline-none placeholder:text-[#92929a]"
                aria-label="Сообщение в поддержку"
              />
              <input ref={fileInput} onChange={(event) => void onAttachment(event)} type="file" accept=".pdf,.doc,.docx,.txt,image/jpeg,image/png,image/webp" className="sr-only" />
              <button type="button" onClick={() => fileInput.current?.click()} className="absolute bottom-3 left-3 flex h-6 w-6 items-center justify-center rounded-full text-[#777780] hover:bg-[#ececef] hover:text-[#37373c] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#a7a7ae]" aria-label="Прикрепить файл"><Paperclip size={13} /></button>
              <button type="button" onClick={() => void send()} disabled={sending || (!text.trim() && !attachment)} className="absolute bottom-3 right-3 flex h-7 w-7 items-center justify-center rounded-full bg-[#62626a] text-white transition-colors hover:bg-[#45454c] disabled:cursor-not-allowed disabled:bg-[#c5c5ca] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8b8b93]" aria-label="Отправить сообщение"><SendHorizontal size={13} /></button>
            </div>
            <p className="mt-1.5 px-1 text-[10px] text-[#92929a]">Enter — отправить · Shift+Enter — новая строка</p>
          </div>
        </section>
      )}
    </>
  );
}
