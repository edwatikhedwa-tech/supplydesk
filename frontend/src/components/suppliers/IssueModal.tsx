import { useState } from 'react';
import { X } from 'lucide-react';

const issueReasons = [
  { value: 'wrong_details', label: 'Неверный ИНН/реквизиты' },
  { value: 'email_invalid', label: 'Письмо не доставляется' },
  { value: 'no_response', label: 'Не отвечает долгое время несмотря на попытки' },
  { value: 'closed', label: 'Компания прекратила деятельность/сменила профиль' },
  { value: 'other', label: 'Другое' },
];

export interface IssueSubmission {
  reason: string;
  comment: string;
  correct_inn?: string;
  blacklist: boolean;
}

export function IssueModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (issue: IssueSubmission) => void }) {
  const [reason, setReason] = useState(issueReasons[0].value);
  const [comment, setComment] = useState('');
  const [correctInn, setCorrectInn] = useState('');
  const [blacklist, setBlacklist] = useState(false);
  const canBlacklist = ['wrong_details', 'email_invalid', 'no_response'].includes(reason);

  return (
    <>
      <div className="fixed inset-0 bg-ink-900/20 z-[60]" onClick={onClose} />
      <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] max-h-[90vh] overflow-y-auto bg-white rounded-2xl shadow-panel z-[70]">
        <div className="px-6 py-5 border-b border-ink-200 flex items-center justify-between sticky top-0 bg-white">
          <h2 className="text-base font-semibold text-ink-900">Сообщить о проблеме</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg text-ink-400 hover:text-ink-800 hover:bg-ink-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div className="space-y-2">
            {issueReasons.map((item) => (
              <label key={item.value} className="flex items-start gap-2.5 text-sm text-ink-700 cursor-pointer">
                <input type="radio" name="issue-reason" checked={reason === item.value} onChange={() => setReason(item.value)} className="mt-0.5 accent-accent-600" />
                {item.label}
              </label>
            ))}
          </div>
          {reason === 'wrong_details' && (
            <div>
              <label className="block text-xs font-medium text-ink-600 mb-1.5">Правильный ИНН, если знаете</label>
              <input
                value={correctInn}
                onChange={(e) => setCorrectInn(e.target.value)}
                className="w-full px-3 py-2.5 text-sm border border-ink-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-200"
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-ink-600 mb-1.5">Комментарий</label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="Расскажите подробнее…"
              className="w-full px-3 py-2.5 text-sm border border-ink-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-accent-200"
            />
          </div>
          {canBlacklist && (
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input type="checkbox" checked={blacklist} onChange={(e) => setBlacklist(e.target.checked)} className="accent-accent-600" />
              Также пометить как чёрный список
            </label>
          )}
        </div>
        <div className="px-6 py-4 border-t border-ink-200 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-ink-500 hover:text-ink-800">Отмена</button>
          <button
            onClick={() => onSubmit({ reason, comment, correct_inn: correctInn || undefined, blacklist })}
            className="px-5 py-2 rounded-xl text-sm font-medium text-white bg-accent-600 hover:bg-accent-700"
          >
            Сохранить сообщение
          </button>
        </div>
      </div>
    </>
  );
}
