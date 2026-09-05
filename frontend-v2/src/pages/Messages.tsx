import {
  Ban,
  ChevronRight,
  Inbox,
  Link2,
  Paperclip,
  Send,
  Sparkles,
  SquareCheck,
  StickyNote,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import { PageHeader } from '../components/shell/PageHeader';
import { Avatar } from '../components/ui/Avatar';
import { Badge, type Tone } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { DeadlineTag } from '../components/ui/DeadlineTag';
import { EmptyState } from '../components/ui/EmptyState';
import { requestGroups as initialGroups, threadMessages as initialMessages, unmatchedMail as initialUnmatched } from '../fixtures/messages';
import { formatDateTime, formatRelativeTime } from '../lib/format';
import type { MailMessage, ThreadSummary, UnmatchedMail } from '../lib/types';

type Selection = { type: 'thread'; id: number } | { type: 'unmatched'; id: number } | null;

const responseTone: Record<ThreadSummary['response_status'], Tone> = {
  none: 'neutral',
  waiting: 'warning',
  answered: 'success',
};

const responseLabel: Record<ThreadSummary['response_status'], string> = {
  none: 'Не отправлено',
  waiting: 'Ожидаем ответ',
  answered: 'Есть ответ',
};

export function Messages() {
  const [groups, setGroups] = useState(initialGroups);
  const [messages, setMessages] = useState(initialMessages);
  const [queue, setQueue] = useState<UnmatchedMail[]>(initialUnmatched);
  const [expanded, setExpanded] = useState<Set<number>>(
    () => new Set(initialGroups.filter((g) => g.threads.some((t) => t.unread_count > 0)).map((g) => g.request_id)),
  );
  const [selection, setSelection] = useState<Selection>(() => {
    const firstUnread = initialGroups.flatMap((g) => g.threads).find((t) => t.unread_count > 0);
    return firstUnread ? { type: 'thread', id: firstUnread.id } : null;
  });
  const [draft, setDraft] = useState('');

  const allThreads = useMemo(() => groups.flatMap((g) => g.threads), [groups]);
  const activeThread = selection?.type === 'thread' ? allThreads.find((t) => t.id === selection.id) ?? null : null;
  const activeGroup = activeThread ? groups.find((g) => g.request_id === activeThread.request_id) ?? null : null;
  const activeUnmatched = selection?.type === 'unmatched' ? queue.find((m) => m.id === selection.id) ?? null : null;

  function toggleGroup(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectThread(threadId: number) {
    setSelection({ type: 'thread', id: threadId });
    setGroups((prev) =>
      prev.map((g) => ({ ...g, threads: g.threads.map((t) => (t.id === threadId ? { ...t, unread_count: 0 } : t)) })),
    );
  }

  function resolveUnmatched(id: number) {
    setQueue((prev) => prev.filter((m) => m.id !== id));
    setSelection((sel) => (sel?.type === 'unmatched' && sel.id === id ? null : sel));
  }

  function sendReply() {
    if (!activeThread || !draft.trim()) return;
    const newMessage: MailMessage = {
      id: Date.now(),
      direction: 'outbound',
      from_email: 'i.kovaleva@technosnab.ru',
      from_name: 'Ирина Ковалёва · ТехноСнаб Инжиниринг',
      to_email: activeThread.supplier_email,
      subject: `Re: ${activeGroup?.request_name ?? ''}`,
      body_text: draft.trim(),
      created_at: new Date().toISOString(),
      status: 'queued',
    };
    setMessages((prev) => ({ ...prev, [activeThread.id]: [...(prev[activeThread.id] ?? []), newMessage] }));
    setDraft('');
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader title="Сообщения" description="Заявка → поставщик → переписка" />
      <div className="flex min-h-0 flex-1">
        <Group orientation="horizontal" className="flex flex-1">
          <Panel defaultSize="30%" minSize="22%" maxSize="42%" className="flex min-w-0 flex-col border-r border-border">
            <div className="flex items-center gap-1 border-b border-border p-2">
              <button className="flex-1 rounded-md bg-accent-subtle px-2.5 py-1.5 text-[12.5px] font-medium text-accent">
                По заявкам
              </button>
              <button
                disabled
                className="flex-1 cursor-not-allowed rounded-md px-2.5 py-1.5 text-[12.5px] font-medium text-ink-faint"
                title="Полный режим почты — скоро"
              >
                Почта
              </button>
            </div>

            <div className="overflow-y-auto">
              <button
                onClick={() => queue[0] && setSelection({ type: 'unmatched', id: queue[0].id })}
                className="flex w-full items-center gap-2.5 border-b border-border px-3 py-2.5 text-left hover:bg-surface-hover"
              >
                <Inbox size={14} className="text-ink-muted" />
                <span className="flex-1 text-[12.5px] font-medium text-ink">Новые письма без заявки</span>
                {queue.length > 0 && <Badge tone="accent">{queue.length}</Badge>}
              </button>
              {selection?.type === 'unmatched' &&
                queue.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => setSelection({ type: 'unmatched', id: m.id })}
                    className={
                      'flex w-full items-start gap-2 border-b border-border py-2 pl-8 pr-3 text-left hover:bg-surface-hover ' +
                      (activeUnmatched?.id === m.id ? 'border-l-2 border-l-accent bg-accent-subtle/40' : '')
                    }
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-ink">{m.subject}</p>
                      <p className="truncate text-[11px] text-ink-muted">{m.from_email}</p>
                    </div>
                    {m.unread && <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />}
                  </button>
                ))}

              {groups.map((g) => {
                const isOpen = expanded.has(g.request_id);
                const unread = g.threads.reduce((s, t) => s + t.unread_count, 0);
                return (
                  <div key={g.request_id} className="border-b border-border">
                    <button
                      onClick={() => toggleGroup(g.request_id)}
                      className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-surface-hover"
                    >
                      <ChevronRight size={13} className={'shrink-0 text-ink-faint transition-transform ' + (isOpen ? 'rotate-90' : '')} />
                      <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-ink">{g.request_name}</span>
                      {unread > 0 && <Badge tone="accent">{unread}</Badge>}
                    </button>
                    {isOpen &&
                      g.threads.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => selectThread(t.id)}
                          className={
                            'flex w-full items-center gap-2 border-t border-border/60 py-2 pl-8 pr-3 text-left hover:bg-surface-hover ' +
                            (activeThread?.id === t.id ? 'border-l-2 border-l-accent bg-accent-subtle/40' : '')
                          }
                        >
                          <Avatar name={t.supplier_name} size="sm" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-[12px] font-medium text-ink">{t.supplier_name}</p>
                            <p className="truncate text-[11px] text-ink-muted">{formatRelativeTime(t.last_message_at)}</p>
                          </div>
                          {t.unread_count > 0 && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />}
                        </button>
                      ))}
                  </div>
                );
              })}
            </div>
          </Panel>

          <Separator className="w-px bg-border transition-colors hover:bg-accent-border" />

          <Panel minSize="35%" className="flex min-w-0 flex-1 flex-col">
            {activeThread && activeGroup ? (
              <>
                <div className="flex items-center gap-3 border-b border-border px-5 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold text-ink">{activeThread.supplier_name}</p>
                    <p className="truncate text-[11.5px] text-ink-muted">{activeGroup.request_name}</p>
                  </div>
                  <Badge tone={responseTone[activeThread.response_status]}>{responseLabel[activeThread.response_status]}</Badge>
                  <DeadlineTag deadline={activeGroup.deadline} />
                </div>

                <div className="flex-1 overflow-y-auto px-5 py-4">
                  {(messages[activeThread.id] ?? []).map((m) => (
                    <div
                      key={m.id}
                      className={
                        'mb-3 max-w-[72ch] rounded-md border-l-2 bg-surface px-4 py-3 ' +
                        (m.direction === 'outbound' ? 'border-l-accent' : 'border-l-border-strong')
                      }
                    >
                      <div className="mb-1.5 flex items-center justify-between gap-3">
                        <span className="truncate text-[12.5px] font-semibold text-ink">{m.from_name}</span>
                        <span className="shrink-0 text-[11px] text-ink-faint">{formatDateTime(m.created_at)}</span>
                      </div>
                      <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink-soft">{m.body_text}</p>
                      {m.attachments && m.attachments.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {m.attachments.map((a) => (
                            <span
                              key={a.filename}
                              className="inline-flex items-center gap-1 rounded border border-border-strong bg-surface-hover px-1.5 py-0.5 text-[11px] text-ink-muted"
                            >
                              <Paperclip size={10} /> {a.filename} · {a.size_kb} КБ
                            </span>
                          ))}
                        </div>
                      )}
                      {m.status === 'queued' && (
                        <p className="mt-1.5 text-[11px] text-ink-faint">Отправляется…</p>
                      )}
                    </div>
                  ))}
                </div>

                <div className="border-t border-border p-3">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    aria-label={`Ответить поставщику ${activeThread.supplier_name}`}
                    placeholder={`Ответить: ${activeThread.supplier_email}`}
                    rows={3}
                    className="w-full resize-none rounded-md border border-border-strong bg-surface px-3 py-2 text-[12.5px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
                  />
                  <div className="mt-2 flex items-center justify-between">
                    <button className="flex h-7 w-7 items-center justify-center rounded-md text-ink-muted hover:bg-surface-hover" title="Прикрепить файл (демо)">
                      <Paperclip size={14} />
                    </button>
                    <Button variant="primary" size="sm" icon={<Send size={13} />} onClick={sendReply} disabled={!draft.trim()}>
                      Отправить
                    </Button>
                  </div>
                </div>
              </>
            ) : activeUnmatched ? (
              <>
                <div className="border-b border-border px-5 py-2.5">
                  <p className="text-[13px] font-semibold text-ink">{activeUnmatched.subject}</p>
                  <p className="text-[11.5px] text-ink-muted">
                    {activeUnmatched.from_email} · {formatRelativeTime(activeUnmatched.received_at)}
                  </p>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-4">
                  <div className="max-w-[72ch] rounded-md border-l-2 border-l-border-strong bg-surface px-4 py-3">
                    <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink-soft">{activeUnmatched.preview}</p>
                  </div>
                </div>
                <div className="border-t border-border p-3">
                  {activeUnmatched.suggestion ? (
                    <div className="mb-2 flex items-center gap-2 rounded-md bg-info-subtle px-3 py-2 text-[12px] text-info">
                      <Link2 size={13} />
                      Похоже на {activeUnmatched.suggestion.supplier_name} · «{activeUnmatched.suggestion.request_name}»
                    </div>
                  ) : null}
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="secondary" size="sm" icon={<Ban size={13} />} onClick={() => resolveUnmatched(activeUnmatched.id)}>
                      Игнорировать
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      icon={<Link2 size={13} />}
                      onClick={() => resolveUnmatched(activeUnmatched.id)}
                    >
                      {activeUnmatched.suggestion ? 'Связать с заявкой' : 'Выбрать заявку…'}
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <EmptyState icon={Inbox} title="Выберите переписку" description="Слева — заявки и письма без привязки." />
            )}
          </Panel>
        </Group>

        <div className="flex w-12 shrink-0 flex-col items-center gap-1 border-l border-border py-3">
          {[
            { icon: StickyNote, label: 'Заметки' },
            { icon: SquareCheck, label: 'Задачи' },
            { icon: Sparkles, label: 'AI' },
          ].map(({ icon: Icon, label }) => (
            <button
              key={label}
              disabled
              title={`${label} — скоро`}
              className="flex h-9 w-9 cursor-not-allowed items-center justify-center rounded-md text-ink-faint"
            >
              <Icon size={16} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
