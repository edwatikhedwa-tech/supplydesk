import { CheckCircle2, Mail, StickyNote } from 'lucide-react';
import { formatDateTime } from '../lib/format';
import type { Task } from '../lib/types';
import type { ThreadNotes } from '../lib/api';

type ActivityItem = { at: string; title: string; detail: string; icon: typeof Mail };

export function ActivityTimeline({ lastMessageAt, notes, tasks }: { lastMessageAt: string | null; notes: ThreadNotes; tasks: Task[] }) {
  const items: ActivityItem[] = [];
  if (lastMessageAt) items.push({ at: lastMessageAt, title: 'Последнее письмо', detail: 'Переписка с поставщиком', icon: Mail });
  for (const note of [notes.workspace, notes.private]) {
    if (note?.note.trim() && note.updated_at) items.push({ at: note.updated_at, title: note.visibility === 'workspace' ? 'Заметка для команды' : 'Личная заметка', detail: note.author_name, icon: StickyNote });
  }
  for (const task of tasks) items.push({ at: task.completed_at || task.created_at, title: task.done ? 'Задача выполнена' : 'Активная задача', detail: task.title, icon: CheckCircle2 });
  const ordered = items.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 8);
  if (!ordered.length) return null;
  return (
    <section className="border-b border-border bg-surface p-3.5">
      <h2 className="mb-2 text-[12.5px] font-semibold text-ink">Активность</h2>
      <ol className="space-y-2">
        {ordered.map((item, index) => {
          const Icon = item.icon;
          return <li key={`${item.at}-${item.title}-${index}`} className="flex gap-2 text-[11.5px]"><Icon size={13} className="mt-0.5 shrink-0 text-ink-muted" aria-hidden="true" /><div className="min-w-0"><p className="truncate font-medium text-ink">{item.title}</p><p className="truncate text-ink-muted">{item.detail} · {formatDateTime(item.at)}</p></div></li>;
        })}
      </ol>
    </section>
  );
}
