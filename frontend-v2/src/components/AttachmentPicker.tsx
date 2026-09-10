import { Paperclip, X } from 'lucide-react';
import { useRef, useState } from 'react';
import { Button } from './ui/Button';
import { formatFileSize } from '../lib/format';
import type { MailAttachment } from '../lib/types';

// Client-side mirror of mail/service.py's validate_attachments() real
// limits -- not invented numbers. Source of truth stays server-side; this
// only avoids a doomed-to-fail round trip for an obviously oversized/wrong
// file.
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_BYTES = 20 * 1024 * 1024;
const ALLOWED_MIME_PREFIXES = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument', 'text/plain', 'image/'];

function isAllowedMime(mime: string): boolean {
  const lower = mime.toLowerCase();
  return ALLOWED_MIME_PREFIXES.some((prefix) => lower === prefix || lower.startsWith(prefix));
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? '');
      const commaIndex = result.indexOf(',');
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error('Не удалось прочитать файл.'));
    reader.readAsDataURL(file);
  });
}

interface AttachmentPickerProps {
  value: MailAttachment[];
  onChange: (next: MailAttachment[]) => void;
  disabled?: boolean;
}

export function AttachmentPicker({ value, onChange, disabled }: AttachmentPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    setLoading(true);
    let runningTotal = value.reduce((sum, a) => sum + (a.size ?? 0), 0);
    const next: MailAttachment[] = [...value];
    let firstError: string | null = null;
    try {
      for (const file of Array.from(files)) {
        if (!file.name || file.name.length > 180 || file.name.includes('/') || file.name.includes('\\')) {
          firstError ??= `«${file.name}»: недопустимое имя файла.`;
          continue;
        }
        const mimeType = file.type || 'application/octet-stream';
        if (!isAllowedMime(mimeType)) {
          firstError ??= `«${file.name}»: тип файла не поддерживается. Разрешены PDF, DOC/DOCX, TXT и изображения.`;
          continue;
        }
        if (file.size > MAX_FILE_BYTES) {
          firstError ??= `«${file.name}»: файл больше 10 МБ.`;
          continue;
        }
        if (runningTotal + file.size > MAX_TOTAL_BYTES) {
          firstError ??= 'Суммарный размер вложений превышает 20 МБ.';
          continue;
        }
        const content_base64 = await readFileAsBase64(file);
        next.push({ filename: file.name, mime_type: mimeType, size: file.size, content_base64 });
        runningTotal += file.size;
      }
      onChange(next);
      if (firstError) setError(firstError);
    } catch {
      setError('Не удалось прочитать один из файлов.');
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <input ref={inputRef} type="file" multiple className="hidden" onChange={(e) => void handleFiles(e.target.files)} aria-label="Прикрепить файл" />
      <Button
        variant="ghost"
        size="sm"
        icon={<Paperclip size={13} />}
        disabled={disabled || loading}
        onClick={() => inputRef.current?.click()}
      >
        {loading ? 'Загружаем…' : 'Прикрепить файл'}
      </Button>
      {value.length > 0 && (
        <ul className="flex flex-col gap-1">
          {value.map((attachment, index) => (
            <li
              key={`${attachment.filename}-${index}`}
              className="flex items-center gap-2 rounded-md border border-border-strong bg-surface px-2 py-1 text-[11.5px]"
            >
              <Paperclip size={11} className="shrink-0 text-ink-faint" />
              <span className="min-w-0 flex-1 truncate text-ink-soft">{attachment.filename}</span>
              <span className="shrink-0 text-ink-faint">{formatFileSize(attachment.size ?? Math.round((attachment.content_base64.length * 3) / 4))}</span>
              <button
                type="button"
                onClick={() => onChange(value.filter((_, i) => i !== index))}
                className="shrink-0 text-ink-faint hover:text-danger"
                aria-label={`Удалить ${attachment.filename}`}
                title="Удалить вложение"
              >
                <X size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="text-[11px] text-danger">{error}</p>}
    </div>
  );
}
