import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import type { RequestListItem } from '@/lib/types';
import { Button, Dialog, Input, Textarea } from '@/components/ui';

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
    <Dialog
      open
      onClose={onClose}
      title="Редактировать заявку"
      actions={<><Button variant="ghost" onClick={onClose}>Отмена</Button><Button variant="primary" onClick={handleSave} disabled={saving}>{saving && <Loader2 size={14} className="animate-spin" />}Сохранить</Button></>}
    >
      <div className="space-y-4">
        <Input label={<>Название <span className="text-rose-500">*</span></>} value={name} onChange={(event) => setName(event.target.value)} error={error || undefined} />
        <Textarea label="Описание" value={description} onChange={(event) => setDescription(event.target.value)} rows={3} />
        <Input label="Дедлайн закупки" type="date" value={deadline} onChange={(event) => setDeadline(event.target.value)} className="max-w-[200px]" />
      </div>
    </Dialog>
  );
}
