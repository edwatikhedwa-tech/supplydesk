import { Link } from 'react-router-dom';
import { Calendar, Check, ChevronRight, Inbox, Mail, MessageSquare, Package, Pencil, RotateCcw, Send, Trash2, Users } from 'lucide-react';
import { formatFullDate, pluralize } from '@/lib/utils';
import type { RequestListItem, RequestStatus } from '@/lib/types';

interface Props {
  request: RequestListItem;
  counts: { found: number; withContacts: number; selected: number; outbound: number; waiting: number; answered: number };
  onRetrySearch?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  deleting?: boolean;
  /** Открыть окно отправки без выбранных поставщиков — чтобы можно было
   *  написать на адрес, введённый вручную (контакт с выставки, из старой
   *  переписки). Плавающая панель появляется только при выборе, поэтому
   *  без этой кнопки такой сценарий был недостижим. */
  onCompose?: () => void;
}

const WORKFLOW_STEPS = [
  { key: 'request', label: 'Заявка' },
  { key: 'search', label: 'Поиск' },
  { key: 'suppliers', label: 'Поставщики' },
  { key: 'queries', label: 'Запросы' },
  { key: 'answers', label: 'Ответы' },
];

const STATUS_TO_STEP: Record<RequestStatus, string> = {
  draft: 'request',
  searching: 'search',
  updating: 'suppliers',
  completed: 'answers',
  error: 'suppliers',
};

const STATUS_BADGE: Record<RequestStatus, { label: string; className: string }> = {
  draft: { label: 'Черновик', className: 'bg-ink-100 text-ink-600' },
  searching: { label: 'Идёт поиск', className: 'bg-accent-50 text-accent-700' },
  updating: { label: 'Обновляется', className: 'bg-accent-50 text-accent-700' },
  completed: { label: 'Завершена', className: 'bg-emerald-50 text-emerald-700' },
  error: { label: 'Ошибка поиска', className: 'bg-rose-50 text-rose-700' },
};

function currentStepIndex(status: RequestStatus, counts: Props['counts']): number {
  // Поисковый статус и рабочий этап закупки — не одно и то же. Когда запрос
  // уже ушёл поставщику, пользователь должен видеть этап «Запросы», даже если
  // у черновика не запускался автоматический поиск.
  if (counts.answered > 0) return WORKFLOW_STEPS.findIndex((step) => step.key === 'answers');
  if (counts.outbound > 0) return WORKFLOW_STEPS.findIndex((step) => step.key === 'queries');
  if (counts.found > 0 && status !== 'searching' && status !== 'error') {
    return WORKFLOW_STEPS.findIndex((step) => step.key === 'suppliers');
  }
  return WORKFLOW_STEPS.findIndex((step) => step.key === STATUS_TO_STEP[status]);
}

export function PageHeader({ request, counts, onRetrySearch, onEdit, onDelete, deleting, onCompose }: Props) {
  const current = currentStepIndex(request.status, counts);
  const queued = request.mail_metrics?.queued ?? 0;
  const acceptedEffective = request.mail_metrics?.accepted_effective ?? request.mail_metrics?.accepted ?? request.sent_count;
  const failed = request.mail_metrics?.failed ?? 0;
  const bounced = request.mail_metrics?.bounced ?? 0;
  const deliveryUnknown = request.mail_metrics?.delivery_unknown ?? 0;
  const acceptedTitle = 'Почтовый сервер принял письмо. Доставка во входящие не гарантируется.';
  // «Черновик» относится к поисковому контуру. Если письмо уже находится в
  // исходящем потоке, этот ярлык больше не описывает рабочее состояние заявки.
  const statusBadge = request.status === 'draft' && counts.outbound > 0
    ? { label: 'В работе', className: 'bg-accent-50 text-accent-700' }
    : STATUS_BADGE[request.status];

  return (
    <header className="border-b border-ink-200/70 bg-white/80 backdrop-blur-sm">
      <div className="mx-auto max-w-[1600px] px-4 pb-4 pt-5 sm:px-6 lg:px-10">
        <nav className="mb-3 flex items-center gap-1.5 text-xs text-ink-500">
          <Link to="/requests" className="cursor-pointer transition-colors hover:text-ink-700">Мои заявки</Link>
          <ChevronRight className="h-3 w-3 text-ink-300" />
          <span className="font-medium text-ink-700">{request.name}</span>
        </nav>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
          <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3 gap-y-2 sm:flex-nowrap">
            <h1 className="sd-shimmer-heading min-w-0 basis-full flex-1 text-page-title font-semibold text-ink-900 sm:basis-auto">{request.name}</h1>
            <span className="text-sm font-medium text-ink-400">№{request.id}</span>
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${statusBadge.className}`}>
              {request.status === 'searching' && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-600" />}
              {statusBadge.label}
            </span>
            {onEdit && (
              <button
                onClick={onEdit}
                title="Редактировать заявку"
                aria-label="Редактировать заявку"
                className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-400 transition-colors hover:bg-ink-100 hover:text-ink-700"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={onDelete}
                disabled={deleting}
                title="Удалить заявку"
                aria-label="Удалить заявку"
                className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:cursor-wait disabled:opacity-50"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
            {onCompose && (
              <button
                onClick={onCompose}
                title="Написать письмо — в том числе на адрес, введённый вручную"
                className="inline-flex items-center gap-1.5 rounded-lg border border-ink-200 px-2.5 py-1 text-xs font-medium text-ink-600 transition-colors hover:border-accent-300 hover:text-accent-700"
              >
                <Send className="h-3.5 w-3.5" />Написать
              </button>
            )}
          </div>
        </div>

        <p className="mt-1 text-xs text-ink-400">
          Заявка №{request.id} · создана {formatFullDate(request.created_at)}
          {request.deadline && (
            <span className="ml-2 inline-flex items-center gap-1 font-medium text-ink-600">
              <Calendar className="h-3 w-3" />дедлайн {new Date(request.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
            </span>
          )}
        </p>
        {request.description && <p className="mt-1 text-xs text-ink-500 max-w-2xl">{request.description}</p>}

        {request.status === 'error' && (
          <div className="mt-3 flex items-center gap-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 max-w-xl">
            <p className="flex-1 text-xs text-rose-700">{request.last_error || 'Поиск завершился с ошибкой.'}</p>
            {onRetrySearch && (
              <button
                onClick={onRetrySearch}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-rose-600 px-2.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-rose-700"
              >
                <RotateCcw className="h-3 w-3" />Повторить поиск
              </button>
            )}
          </div>
        )}

        {request.status === 'searching' && request.search_total > 0 && (
          <div className="mt-3 max-w-sm">
            <div className="mb-1 flex items-center justify-between text-xs text-ink-500">
              <span>Обрабатывается позиция {Math.min(request.search_progress + 1, request.search_total)} из {request.search_total}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
              <div
                className="h-full rounded-full bg-accent-600 transition-all"
                style={{ width: `${Math.min(100, (request.search_progress / request.search_total) * 100)}%` }}
              />
            </div>
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <span className="inline-flex items-center gap-1.5">
            <span className="text-ink-400"><Package className="h-3.5 w-3.5" /></span>
            <span className="font-medium text-ink-600">{request.positions_count} {pluralize(request.positions_count, 'позиция', 'позиции', 'позиций')}</span>
          </span>
          <span className="text-ink-300">·</span>
          <span className="inline-flex items-center gap-1.5" title="Количество карточек компаний в этой заявке">
            <span className="text-ink-400"><Users className="h-3.5 w-3.5" /></span>
            <span className="font-medium text-ink-600">{counts.found} {pluralize(counts.found, 'компания', 'компании', 'компаний')}</span>
          </span>
          <span className="text-ink-300">·</span>
          <span className="inline-flex items-center gap-1.5" title="Карточки компаний, у которых есть хотя бы один email">
            <span className="text-ink-400"><Mail className="h-3.5 w-3.5" /></span>
            <span className="font-medium text-ink-700">{counts.withContacts} с контактами</span>
          </span>
          <span className="text-ink-300">·</span>
          <span className="inline-flex items-center gap-1.5" title="Карточки компаний с отправленным письмом без ответа">
            <span className="text-ink-400"><MessageSquare className="h-3.5 w-3.5" /></span>
            <span className="font-medium text-amber-700">{counts.waiting} {counts.waiting === 1 ? 'компания ждёт' : 'компаний ждут'} ответа</span>
          </span>
          <span className="text-ink-300">·</span>
          <span className="inline-flex items-center gap-1.5" title="Карточки компаний с ответом хотя бы на один контакт">
            <span className="text-ink-400"><Inbox className="h-3.5 w-3.5" /></span>
            <span className="font-medium text-emerald-600">{counts.answered} компаний с ответом</span>
          </span>
          <span className="text-ink-300">·</span>
          <span className="inline-flex flex-wrap items-center gap-1.5" data-request-mail-metrics title="Счётчики сообщений, а не карточек компаний">
            <span className="text-ink-400"><MessageSquare className="h-3.5 w-3.5" /></span>
            <span className="font-medium text-ink-600">Письма:</span>
            <span className="font-medium text-amber-700">{queued} {queued === 1 ? 'ожидает' : 'ожидают'} отправки</span>
            <span className="text-ink-300">·</span>
            <span className="font-medium text-accent-700" title={acceptedTitle}>
              {acceptedEffective} отправлено
            </span>
            <span className="text-ink-300">·</span>
            <span className="font-medium text-rose-700">{failed} {failed === 1 ? 'ошибка' : 'ошибки'} отправки</span>
            {bounced > 0 && <><span className="text-ink-300">·</span><span className="font-medium text-rose-800">{bounced} не доставлено</span></>}
            {deliveryUnknown > 0 && <><span className="text-ink-300">·</span><span className="font-medium text-orange-800">{deliveryUnknown} статус неизвестен</span></>}
          </span>
        </div>

        <div className="mt-4">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-1">
            {WORKFLOW_STEPS.map((step, index) => {
              const done = index < current;
              const active = index === current;
              return (
                <div key={step.key} className="flex shrink-0 items-center gap-1">
                  {index > 0 && <div className={`hidden h-px w-6 sm:block ${index <= current ? 'bg-accent-500' : 'bg-ink-200'}`} />}
                  <div
                    data-workflow-step={step.key}
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-all ${
                      active ? 'bg-accent-600 text-white shadow-sm' : done ? 'bg-accent-50 text-accent-700' : 'bg-ink-100 text-ink-400'
                    }`}
                  >
                    {done ? (
                      <Check className="h-3 w-3" />
                    ) : (
                      <span className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-white' : 'bg-ink-300'}`} />
                    )}
                    {step.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </header>
  );
}
