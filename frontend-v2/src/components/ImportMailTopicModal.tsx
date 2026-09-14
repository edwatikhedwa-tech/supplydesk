import { ArrowRight, CheckCircle2, FileText, FolderSearch, Loader2, Mail, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { ApiError, api } from '../lib/api';
import type { MailTopicPreview } from '../lib/types';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
}

export function ImportMailTopicModal({
  onClose,
  onImported,
  onOpenExisting,
}: {
  onClose: () => void;
  onImported: (requestId: number) => void;
  onOpenExisting: (requestId: number) => void;
}) {
  const [subject, setSubject] = useState('');
  const [preview, setPreview] = useState<MailTopicPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');

  async function findMail() {
    if (!subject.trim()) {
      setError('Введите тему письма.');
      return;
    }
    setPreviewing(true);
    setError('');
    setPreview(null);
    try {
      setPreview(await api.mailTopicPreview(subject.trim()));
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Не удалось проверить почту.');
    } finally {
      setPreviewing(false);
    }
  }

  async function importMail() {
    if (!preview || preview.count === 0 || preview.existing_request_id) return;
    setImporting(true);
    setError('');
    try {
      const result = await api.importMailTopic(preview.subject);
      onImported(result.request_id);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Не удалось создать заявку из переписки.');
      setImporting(false);
    }
  }

  return (
    <Modal title="Импортировать переписку" onClose={onClose} width={640}>
      <div className="space-y-4">
        <div className="rounded-lg border border-accent-border bg-accent-subtle/50 px-3.5 py-3">
          <div className="flex items-start gap-2.5">
            <FolderSearch size={17} className="mt-0.5 shrink-0 text-accent" />
            <div>
              <p className="text-[12.5px] font-medium text-ink">Создать заявку из уже начатой переписки</p>
              <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-muted">
                Сначала будут прочитаны только заголовки совпавших писем из «Входящих» и «Отправленных». Текст писем и новый черновик появятся только после вашего подтверждения.
              </p>
            </div>
          </div>
        </div>

        <div>
          <label htmlFor="mail-topic-subject" className="mb-1 block text-[12px] font-medium text-ink-soft">Тема письма</label>
          <div className="flex gap-2">
            <input
              id="mail-topic-subject"
              value={subject}
              onChange={(event) => {
                setSubject(event.target.value);
                setPreview(null);
                setError('');
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void findMail();
              }}
              placeholder="Например: [SD-1061] Проверка запроса"
              autoFocus
              className="h-9 min-w-0 flex-1 rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
            <Button variant="secondary" icon={previewing ? <Loader2 size={14} className="animate-spin" /> : <FolderSearch size={14} />} disabled={previewing || importing} onClick={() => void findMail()}>
              Найти
            </Button>
          </div>
        </div>

        {preview && (
          <div className="space-y-3">
            {preview.existing_request_id ? (
              <div className="flex items-start gap-2 rounded-md border border-warning-border bg-warning-subtle px-3 py-2.5 text-[12px] text-warning">
                <TriangleAlert size={15} className="mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p>Метка {preview.email_reference} уже принадлежит заявке №{preview.existing_request_id}.</p>
                  <button type="button" onClick={() => onOpenExisting(preview.existing_request_id!)} className="mt-1 inline-flex items-center gap-1 font-medium underline underline-offset-2">
                    Открыть существующую заявку <ArrowRight size={13} />
                  </button>
                </div>
              </div>
            ) : preview.count === 0 ? (
              <div className="rounded-md border border-border bg-surface-hover px-3 py-2.5 text-[12px] text-ink-muted">
                В подключённых ящиках нет писем с этой темой. Черновик не будет создан.
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[12.5px] font-medium text-ink">Найдено писем: {preview.count}</p>
                  {preview.email_reference && <span className="rounded-md bg-surface-hover px-2 py-1 font-mono text-[10.5px] text-ink-soft">{preview.email_reference}</span>}
                </div>
                <div className="max-h-48 divide-y divide-border overflow-y-auto rounded-md border border-border bg-surface">
                  {preview.items.map((item, index) => (
                    <div key={`${item.account_id}-${item.folder}-${item.received_at}-${index}`} className="flex min-w-0 items-start gap-2.5 px-3 py-2">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-surface-hover text-ink-muted" title={item.direction === 'outbound' ? 'Отправленное' : 'Входящее'}>
                        {item.direction === 'outbound' ? <FileText size={12} /> : <Mail size={12} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12px] text-ink" title={item.direction === 'outbound' ? item.to_email : item.from_email}>
                          {item.direction === 'outbound' ? `Кому: ${item.to_email}` : `От: ${item.from_email}`}
                        </p>
                        <p className="truncate text-[10.5px] text-ink-faint" title={`${item.folder} · ${item.account_email}`}>{item.folder} · {item.account_email}</p>
                      </div>
                      <time className="shrink-0 text-[10.5px] text-ink-faint">{formatDate(item.received_at)}</time>
                    </div>
                  ))}
                </div>
                <div className="flex items-start gap-2 rounded-md bg-success-subtle px-3 py-2.5 text-[11.5px] text-success">
                  <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
                  <p>Будет создан черновик заявки и добавлены все {preview.count} найденных писем. Для новых адресов появятся карточки корреспондентов, которые можно переименовать позже.</p>
                </div>
              </>
            )}
            {preview.errors.length > 0 && (
              <p className="text-[11.5px] text-warning">Не удалось проверить: {preview.errors.map((item) => item.account_email).filter(Boolean).join(', ')}. Остальные подключённые ящики проверены.</p>
            )}
          </div>
        )}

        {error && <p role="alert" className="text-[12px] text-danger">{error}</p>}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" disabled={previewing || importing} onClick={onClose}>Отмена</Button>
          <Button
            variant="primary"
            icon={importing ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
            disabled={!preview || preview.count === 0 || Boolean(preview.existing_request_id) || previewing || importing}
            onClick={() => void importMail()}
          >
            Создать черновик и импортировать
          </Button>
        </div>
      </div>
    </Modal>
  );
}
