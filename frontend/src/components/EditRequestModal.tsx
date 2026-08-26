import { useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import type { RequestListItem } from '@/lib/types';

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/20 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-ink-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-100">
          <h3 className="text-base font-semibold text-ink-900">Редактировать заявку</h3>
          <button onClick={onClose} className="p-1.5 -mr-1.5 text-ink-400 hover:text-ink-900 hover:bg-ink-100 rounded-lg transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-bold text-ink-700">
              Название <span className="text-rose-500">*</span>
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-10 w-full rounded-lg border border-ink-200 bg-ink-50/60 px-3 text-sm text-ink-800 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-bold text-ink-700">Описание</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full resize-none rounded-lg border border-ink-200 bg-ink-50/60 px-3 py-2.5 text-sm text-ink-800 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-bold text-ink-700">Дедлайн закупки</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="h-10 w-full max-w-[200px] rounded-lg border border-ink-200 bg-ink-50/60 px-3 text-sm text-ink-800 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
            />
          </div>
          {error && <p className="text-xs font-medium text-rose-600">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-ink-100 bg-ink-50">
          <button onClick={onClose} className="px-3.5 py-2 text-sm font-medium text-ink-600 hover:text-ink-900 rounded-lg transition-colors">
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white bg-accent-600 hover:bg-accent-700 rounded-lg transition-colors disabled:opacity-50"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
}
