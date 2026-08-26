import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ChevronRight, Plus, Save, Search, X } from 'lucide-react';
import { ApiError, api } from '@/lib/api';

interface DraftItem { id: string; name: string; }

let draftItemSeq = 0;
const makeDraftItem = (): DraftItem => ({ id: `draft-${Date.now()}-${draftItemSeq++}`, name: '' });

export function NewRequest() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [deadline, setDeadline] = useState('');
  const [items, setItems] = useState<DraftItem[]>([makeDraftItem()]);
  const [titleError, setTitleError] = useState(false);
  const [itemsError, setItemsError] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const updateItem = (id: string, value: string) => {
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, name: value } : item)));
  };

  const addItem = () => setItems((prev) => [...prev, makeDraftItem()]);
  const removeItem = (id: string) => setItems((prev) => (prev.length > 1 ? prev.filter((item) => item.id !== id) : prev));

  const filledItems = items.map((item) => ({ name: item.name.trim() })).filter((item) => item.name);

  const handleSubmit = async (status: 'draft' | 'searching') => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setTitleError(true);
      return;
    }
    if (status === 'searching' && filledItems.length === 0) {
      setItemsError(true);
      return;
    }
    setSubmitError('');
    setSubmitting(true);
    try {
      const created = await api.createRequest({
        name: trimmedTitle,
        description: description.trim() || undefined,
        deadline: deadline || undefined,
        positions: filledItems,
      });
      if (status === 'searching') {
        await api.startRequestSearch(created.request_id);
      }
      navigate(`/requests/${created.request_id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Не удалось создать заявку');
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen px-6 py-7 lg:px-10 lg:py-10 animate-fade-in">
      <div className="mx-auto max-w-[760px] space-y-6">
        <nav className="flex items-center gap-1.5 text-xs text-ink-500">
          <Link to="/requests" className="transition-colors hover:text-ink-700">Мои заявки</Link>
          <ChevronRight className="h-3 w-3 text-ink-300" />
          <b className="text-ink-700">Новая заявка</b>
        </nav>

        <div>
          <h1 className="text-[28px] font-bold tracking-tight">Новая заявка</h1>
          <p className="mt-1 text-sm text-ink-500">Опишите, что нужно найти — остальное сделает поиск поставщиков.</p>
        </div>

        <div className="space-y-6 rounded-2xl border border-ink-200/80 bg-white p-6 shadow-soft animate-slide-up">
          <div>
            <label className="mb-1.5 block text-xs font-bold text-ink-700">
              Название заявки <span className="text-rose-500">*</span>
            </label>
            <input
              value={title}
              onChange={(e) => { setTitle(e.target.value); if (e.target.value.trim()) setTitleError(false); }}
              placeholder="Например: Строительные материалы"
              className={`h-11 w-full rounded-xl border bg-ink-50/60 px-3.5 text-sm text-ink-800 placeholder:text-ink-400 transition-all focus:bg-white focus:outline-none focus:ring-2 ${
                titleError ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-100' : 'border-ink-200 focus:border-accent-400 focus:ring-accent-100'
              }`}
            />
            {titleError && <p className="mt-1.5 text-xs font-medium text-rose-600">Укажите название заявки</p>}
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-bold text-ink-700">Описание</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Кратко опишите контекст заявки — необязательно"
              rows={3}
              className="w-full resize-none rounded-xl border border-ink-200 bg-ink-50/60 px-3.5 py-3 text-sm text-ink-800 placeholder:text-ink-400 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-bold text-ink-700">Дедлайн закупки</label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="h-11 w-full max-w-[220px] rounded-xl border border-ink-200 bg-ink-50/60 px-3.5 text-sm text-ink-800 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
            />
            <p className="mt-1.5 text-xs text-ink-400">Необязательно — к какому сроку нужны предложения от поставщиков.</p>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="block text-xs font-bold text-ink-700">Позиции</label>
              {itemsError && <span className="text-xs font-medium text-rose-600">Добавьте хотя бы одну позицию</span>}
            </div>
            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.id} className="flex items-center gap-2 animate-fade-in">
                  <input
                    value={item.name}
                    onChange={(e) => { updateItem(item.id, e.target.value); if (e.target.value.trim()) setItemsError(false); }}
                    placeholder="Например: Кирпич М150"
                    className="h-10 flex-1 rounded-xl border border-ink-200 bg-ink-50/60 px-3.5 text-sm text-ink-800 placeholder:text-ink-400 transition-all focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
                  />
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center">
                    {items.length > 1 && (
                      <button
                        onClick={() => removeItem(item.id)}
                        className="flex h-10 w-10 items-center justify-center rounded-xl text-ink-400 transition hover:bg-rose-50 hover:text-rose-600"
                        aria-label="Удалить позицию"
                      >
                        <X size={16} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={addItem}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold text-accent-600 transition hover:bg-accent-50"
            >
              <Plus size={14} />Добавить позицию
            </button>
          </div>
        </div>

        {submitError && <p className="text-right text-xs font-medium text-rose-600">{submitError}</p>}
        <div className="flex flex-col-reverse justify-end gap-3 sm:flex-row">
          <button
            onClick={() => handleSubmit('draft')}
            disabled={submitting}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-ink-200 bg-white px-5 py-3 text-sm font-bold text-ink-700 shadow-soft transition hover:border-ink-300 hover:bg-ink-50 disabled:opacity-50"
          >
            <Save size={16} />Сохранить черновик
          </button>
          <button
            onClick={() => handleSubmit('searching')}
            disabled={submitting}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent-600 px-5 py-3 text-sm font-bold text-white shadow-panel transition hover:-translate-y-0.5 hover:bg-accent-700 hover:shadow-float disabled:opacity-50"
          >
            <Search size={16} />Начать поиск поставщиков
          </button>
        </div>
      </div>
    </div>
  );
}
