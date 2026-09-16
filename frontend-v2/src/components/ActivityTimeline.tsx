import { CheckCircle2, Mail, StickyNote } from 'lucide-react';
import { formatDateTime } from '../lib/format';
import type { Task } from '../lib/types';
import type { ThreadNotes } from '../lib/api';

type ActivityItem = { at: string; title: string; detail: string; subDetail?: string; icon: typeof Mail };

/** Compact activity feed inside SupplierCardPanel. Task/note/request text is
 * real, user-authored content of unpredictable length -- it must stay
 * readable (wrap onto 2-3 lines, never a single-line ellipsis that hides
 * the point of the entry) and never force the panel into horizontal
 * scroll. The task's own action text and the заявка it belongs to are
 * shown as two visually distinct lines, not one run-on sentence. */
export function ActivityTimeline({ lastMessageAt, notes, tasks }: { lastMessageAt: string | null; notes: ThreadNotes; tasks: Task[] }) {
  const items: ActivityItem[] = [];
  if (lastMessageAt) items.push({ at: lastMessageAt, title: 'Последнее письмо', detail: 'Переписка с поставщиком', icon: Mail });
  for (const note of [notes.workspace, notes.private]) {
    if (note?.note.trim() && note.updated_at) items.push({ at: note.updated_at, title: note.visibility === 'workspace' ? 'Заметка для команды' : 'Личная заметка', detail: note.author_name, icon: StickyNote });
  }
  for (const task of tasks) {
    items.push({
      at: task.completed_at || task.created_at,
      title: task.done ? 'Задача выполнена' : 'Активная задача',
      detail: task.title,
      subDetail: task.request_name ? `Заявка «${task.request_name}»` : undefined,
      icon: CheckCircle2,
    });
  }
  const ordered = items.sort((a, b) => b.at.localeCompare(a.at)).slice(0, 8);
  if (!ordered.length) return null;
  return (
    <section className="border-b border-border bg-surface p-3.5">
      <h2 className="mb-2 text-[12.5px] font-semibold text-ink">Активность</h2>
      <ol className="space-y-3">
        {ordered.map((item, index) => {
          const Icon = item.icon;
          return (
            <li key={`${item.at}-${item.title}-${index}`} className="flex gap-2 text-[11.5px]">
              <Icon size={13} className="mt-0.5 shrink-0 text-ink-muted" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink">{item.title}</p>
                <p className="line-clamp-3 break-words text-ink-muted" title={item.detail}>
                  {item.detail}
                </p>
                {item.subDetail && (
                  <p className="line-clamp-2 break-words text-ink-faint" title={item.subDetail}>
                    {item.subDetail}
                  </p>
                )}
                <p className="mt-0.5 text-[10.5px] text-ink-faint">{formatDateTime(item.at)}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
