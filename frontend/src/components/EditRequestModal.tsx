import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import type { RequestListItem } from '@/lib/types';
import {
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Textarea,
} from '@/components/ui';

interface Props {
  request: RequestListItem;
  onClose: () => void;
  onSaved: () => void;
}

export function EditRequestModal({ request, onClose, onSaved }: Props) {
  const [name, setName] = useState(request.name);
  const [description, setDescription] = useState(request.description || '');
  const [deadline, setDeadline] = useState(request.deadline || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const handleSave = async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError('Название заявки обязательно');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api.updateRequest(request.id, { name: trimmed, description, deadline });
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось сохранить изменения');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[min(720px,calc(100vh-32px))] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Редактировать заявку</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="edit-request-name" className="text-xs font-semibold text-ink-700">Название <span className="text-rose-500">*</span></label>
            <Input id="edit-request-name" value={name} onChange={(event) => setName(event.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? 'edit-request-name-error' : undefined} />
            {error && <p id="edit-request-name-error" role="alert" className="text-xs font-medium text-rose-700">{error}</p>}
          </div>
          <Textarea label="Описание" value={description} onChange={(event) => setDescription(event.target.value)} rows={3} />
          <div className="space-y-1.5">
            <label htmlFor="edit-request-deadline" className="text-xs font-semibold text-ink-700">Дедлайн закупки</label>
            <Input id="edit-request-deadline" type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} className="max-w-[200px]" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button variant="primary" onClick={handleSave} disabled={saving}>{saving && <Loader2 size={14} className="animate-spin" />}Сохранить</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
