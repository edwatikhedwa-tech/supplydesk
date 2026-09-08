import { AlertTriangle, Plus, Save, Search, X } from 'lucide-react';
import { useState } from 'react';
import { ApiError, api } from '../lib/api';
import { Button } from './ui/Button';
import { Modal } from './ui/Modal';

interface DraftItem {
  id: string;
  name: string;
}

let draftItemSeq = 0;
const makeDraftItem = (): DraftItem => ({ id: `draft-${Date.now()}-${draftItemSeq++}`, name: '' });

const SEARCH_DEPTH_MIN = 1;
const SEARCH_DEPTH_MAX = 100;

export function NewRequestModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [deadline, setDeadline] = useState('');
  const [searchDepth, setSearchDepth] = useState('1');
  const [searchDepthError, setSearchDepthError] = useState('');
  const [deepConfirming, setDeepConfirming] = useState(false);
  const [items, setItems] = useState<DraftItem[]>([makeDraftItem()]);
  const [titleError, setTitleError] = useState(false);
  const [itemsError, setItemsError] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const updateItem = (id: string, value: string) => setItems((prev) => prev.map((item) => (item.id === id ? { ...item, name: value } : item)));
  const addItem = () => setItems((prev) => [...prev, makeDraftItem()]);
  const removeItem = (id: string) => setItems((prev) => (prev.length > 1 ? prev.filter((item) => item.id !== id) : prev));

  const filledItems = items.map((item) => ({ name: item.name.trim() })).filter((item) => item.name);
  const parsedSearchDepth = Number(searchDepth);
  const searchDepthIsValid = Number.isInteger(parsedSearchDepth) && parsedSearchDepth >= SEARCH_DEPTH_MIN && parsedSearchDepth <= SEARCH_DEPTH_MAX;
  const estimatedSearchPages = searchDepthIsValid ? parsedSearchDepth * Math.max(filledItems.length, 1) : 0;

  async function handleSubmit(status: 'draft' | 'searching', deepConfirmed = false) {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      setTitleError(true);
      return;
    }
    if (status === 'searching' && filledItems.length === 0) {
      setItemsError(true);
      return;
    }
    if (!searchDepthIsValid) {
      setSearchDepthError(`Введите целое число от ${SEARCH_DEPTH_MIN} до ${SEARCH_DEPTH_MAX}`);
      return;
    }
    if (status === 'searching' && parsedSearchDepth > 5 && !deepConfirmed) {
      setDeepConfirming(true);
      return;
    }
    setSubmitError('');
    setSubmitting(true);
    try {
      const created = await api.createRequest({
        name: trimmedTitle,
        description: description.trim() || undefined,
        deadline: deadline || undefined,
        search_depth: parsedSearchDepth,
        positions: filledItems,
      });
      if (status === 'searching') await api.startRequestSearch(created.request_id);
      onCreated();
      onClose();
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Не удалось создать заявку');
      setSubmitting(false);
    }
  }

  return (
    <Modal title="Новая заявка" onClose={onClose} width={560}>
      <div className="space-y-4">
        <div>
          <label htmlFor="request-title" className="mb-1 block text-[12px] font-medium text-ink-soft">
            Название заявки <span className="text-danger">*</span>
          </label>
          <input
            id="request-title"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              if (e.target.value.trim()) setTitleError(false);
            }}
            placeholder="Например: Строительные материалы"
            autoFocus
            className={
              'h-9 w-full rounded-md border bg-surface px-3 text-[13px] outline-none focus:ring-1 ' +
              (titleError ? 'border-danger-border focus:border-danger focus:ring-danger-border' : 'border-border-strong focus:border-accent focus:ring-accent-border')
            }
          />
          {titleError && <p className="mt-1 text-[11.5px] text-danger">Укажите название заявки</p>}
        </div>

        <div>
          <label htmlFor="request-description" className="mb-1 block text-[12px] font-medium text-ink-soft">
            Описание
          </label>
          <textarea
            id="request-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Кратко опишите контекст заявки — необязательно"
            rows={2}
            className="w-full resize-none rounded-md border border-border-strong bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
          />
        </div>

        <div className="flex gap-4">
          <div>
            <label htmlFor="request-deadline" className="mb-1 block text-[12px] font-medium text-ink-soft">
              Дедлайн
            </label>
            <input
              id="request-deadline"
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="h-9 w-[170px] rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
          </div>
          <div>
            <label htmlFor="search-depth" className="mb-1 block text-[12px] font-medium text-ink-soft">
              Глубина поиска
            </label>
            <input
              id="search-depth"
              type="number"
              inputMode="numeric"
              min={SEARCH_DEPTH_MIN}
              max={SEARCH_DEPTH_MAX}
              step={1}
              value={searchDepth}
              onChange={(e) => {
                setSearchDepth(e.target.value);
                setSearchDepthError('');
                setDeepConfirming(false);
              }}
              aria-invalid={Boolean(searchDepthError)}
              className={
                'h-9 w-[110px] rounded-md border bg-surface px-3 text-[13px] outline-none focus:ring-1 ' +
                (searchDepthError ? 'border-danger-border focus:border-danger focus:ring-danger-border' : 'border-border-strong focus:border-accent focus:ring-accent-border')
              }
            />
          </div>
        </div>
        {searchDepthError && <p className="text-[11.5px] text-danger">{searchDepthError}</p>}
        <p className="text-[11.5px] text-ink-muted">
          {searchDepthIsValid
            ? `До ${estimatedSearchPages} поисковых страниц для ${Math.max(filledItems.length, 1)} ${filledItems.length === 1 ? 'позиции' : 'позиций'}.`
            : 'От 1 до 100 страниц выдачи на каждую позицию.'}
        </p>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="block text-[12px] font-medium text-ink-soft">Позиции</label>
            {itemsError && <span className="text-[11.5px] text-danger">Добавьте хотя бы одну позицию</span>}
          </div>
          <div className="space-y-1.5">
            {items.map((item, index) => (
              <div key={item.id} className="flex items-center gap-1.5">
                <input
                  aria-label={`Позиция ${index + 1}`}
                  value={item.name}
                  onChange={(e) => {
                    updateItem(item.id, e.target.value);
                    if (e.target.value.trim()) setItemsError(false);
                  }}
                  placeholder="Например: Кирпич М150"
                  className="h-9 flex-1 rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
                />
                {items.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeItem(item.id)}
                    aria-label="Удалить позицию"
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-ink-faint hover:bg-danger-subtle hover:text-danger"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={addItem}
            className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-medium text-accent hover:bg-accent-subtle"
          >
            <Plus size={13} />
            Добавить позицию
          </button>
        </div>

        {deepConfirming && (
          <div role="alert" className="flex items-start gap-2 rounded-md border border-warning-border bg-warning-subtle px-3 py-2.5 text-[12px] text-warning">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <div className="flex-1">
              Глубина {parsedSearchDepth}: до {estimatedSearchPages} страниц выдачи — займёт больше времени и внешней квоты.
            </div>
            <Button size="sm" variant="secondary" disabled={submitting} onClick={() => void handleSubmit('searching', true)}>
              Подтвердить
            </Button>
          </div>
        )}
        {submitError && <p className="text-[12px] text-danger">{submitError}</p>}

        <div className="flex justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" icon={<Save size={13} />} disabled={submitting} onClick={() => void handleSubmit('draft')}>
            Сохранить черновик
          </Button>
          <Button variant="primary" icon={<Search size={13} />} disabled={submitting} onClick={() => void handleSubmit('searching')}>
            Начать поиск поставщиков
          </Button>
        </div>
      </div>
    </Modal>
  );
}
