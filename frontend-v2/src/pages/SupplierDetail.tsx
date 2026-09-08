import {
  ArrowLeft,
  Ban,
  Building2,
  Check,
  ExternalLink,
  Mail,
  MessageSquareText,
  Phone,
  ShieldCheck,
  Star,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { QuickAddTaskButton } from '../components/QuickAddTaskButton';
import { Badge, type Tone } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { checkoUrl, companyAge, formatCompanyName, formatDateTime, formatMoney, formatPercent } from '../lib/format';
import { useApiData } from '../lib/useApiData';

const outcomeMeta: Record<string, { label: string; tone: Tone }> = {
  not_sent: { label: 'Не отправлено', tone: 'neutral' },
  sent: { label: 'Отправлено', tone: 'warning' },
  waiting: { label: 'Ждём ответа', tone: 'warning' },
  answered: { label: 'Есть ответ', tone: 'success' },
  error: { label: 'Ошибка', tone: 'danger' },
  delivery_unknown: { label: 'Статус неизвестен', tone: 'warning' },
};

export function SupplierDetail() {
  const { id } = useParams<{ id: string }>();
  const supplierId = Number(id);
  const navigate = useNavigate();
  const state = useApiData(() => api.getGlobalSupplierDetail(supplierId), [supplierId]);

  const [note, setNote] = useState('');
  const [noteLoaded, setNoteLoaded] = useState(false);
  const [noteSaveState, setNoteSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const noteSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [relationshipBusy, setRelationshipBusy] = useState(false);
  const [relationshipError, setRelationshipError] = useState('');
  const [blacklistReasonOpen, setBlacklistReasonOpen] = useState(false);
  const [blacklistReason, setBlacklistReason] = useState('');

  useEffect(() => {
    if (state.status === 'ready') {
      setNote(state.data.note);
      setNoteLoaded(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status === 'ready' ? state.data.id : null]);

  if (!id || Number.isNaN(supplierId)) {
    return <EmptyState icon={Ban} title="Некорректный номер поставщика" />;
  }
  if (state.status === 'loading') return <LoadingState label="Загружаем поставщика…" />;
  if (state.status === 'error') return <ErrorState message={state.message} onRetry={state.reload} />;

  const supplier = state.data;

  function handleNoteChange(value: string) {
    setNote(value);
    setNoteSaveState('idle');
    if (noteSaveTimer.current) clearTimeout(noteSaveTimer.current);
    noteSaveTimer.current = setTimeout(() => {
      setNoteSaveState('saving');
      api
        .saveGlobalSupplierNote(supplierId, value)
        .then(() => setNoteSaveState('saved'))
        .catch(() => setNoteSaveState('idle'));
    }, 500);
  }

  async function setRelationship(status: 'none' | 'favorite' | 'blacklisted', reason = '') {
    setRelationshipBusy(true);
    setRelationshipError('');
    try {
      await api.setGlobalSupplierRelationship(supplierId, status, reason);
      setBlacklistReasonOpen(false);
      setBlacklistReason('');
      state.reload();
    } catch (e) {
      setRelationshipError(e instanceof ApiError ? e.message : 'Не удалось изменить статус.');
    } finally {
      setRelationshipBusy(false);
    }
  }

  const isFavorite = supplier.relationship_status === 'favorite';
  const isBlacklisted = supplier.relationship_status === 'blacklisted';

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="flex items-center gap-2 px-6 pt-5">
        <Link to="/suppliers" className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink">
          <ArrowLeft size={13} />
          Поставщики
        </Link>
      </div>

      <div className="flex items-start justify-between gap-4 px-6 pb-4 pt-2">
        <div className="min-w-0">
          <h1 className="font-display text-[19px] font-semibold leading-tight text-ink">{formatCompanyName(supplier.name)}</h1>
          <p className="mt-0.5 text-[12.5px] text-ink-muted">ИНН {supplier.inn}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isBlacklisted && <Badge tone="danger">В чёрном списке</Badge>}
          {isFavorite && <Badge tone="accent">Избранный</Badge>}
          <QuickAddTaskButton supplierId={supplierId} />
          <Button
            variant={isFavorite ? 'primary' : 'secondary'}
            size="sm"
            icon={<Star size={13} />}
            disabled={relationshipBusy}
            onClick={() => setRelationship(isFavorite ? 'none' : 'favorite')}
          >
            {isFavorite ? 'В избранном' : 'В избранное'}
          </Button>
          {isBlacklisted ? (
            <Button variant="secondary" size="sm" icon={<Check size={13} />} disabled={relationshipBusy} onClick={() => setRelationship('none')}>
              Убрать из ЧС
            </Button>
          ) : (
            <Button variant="secondary" size="sm" icon={<Ban size={13} />} onClick={() => setBlacklistReasonOpen((v) => !v)}>
              В чёрный список
            </Button>
          )}
        </div>
      </div>

      {blacklistReasonOpen && (
        <div className="mx-6 mb-4 rounded-md border border-border bg-surface-hover p-3">
          <label className="mb-1 block text-[12px] font-medium text-ink-soft">Причина (обязательно для чёрного списка)</label>
          <div className="flex items-center gap-2">
            <input
              autoFocus
              value={blacklistReason}
              onChange={(e) => setBlacklistReason(e.target.value)}
              placeholder="Например: не отвечает на запросы, срывает сроки…"
              className="h-9 flex-1 rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
            <Button variant="secondary" size="sm" onClick={() => setBlacklistReasonOpen(false)}>
              Отмена
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={!blacklistReason.trim() || relationshipBusy}
              onClick={() => setRelationship('blacklisted', blacklistReason.trim())}
            >
              Подтвердить
            </Button>
          </div>
        </div>
      )}
      {relationshipError && <p className="mx-6 mb-3 text-[12px] text-danger">{relationshipError}</p>}

      <div className="grid grid-cols-1 gap-4 px-6 pb-6 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <section className="rounded-lg border border-border bg-surface">
            <h2 className="border-b border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink">Контакты и реквизиты</h2>
            <div className="grid grid-cols-2 gap-3 p-4 text-[12.5px]">
              <div className="flex items-center gap-2 text-ink-soft">
                <Mail size={13} className="shrink-0 text-ink-faint" />
                {supplier.email ? <a href={`mailto:${supplier.email}`} className="hover:text-accent">{supplier.email}</a> : <span className="text-ink-faint">—</span>}
              </div>
              <div className="flex items-center gap-2 text-ink-soft">
                <Phone size={13} className="shrink-0 text-ink-faint" />
                {supplier.phone || <span className="text-ink-faint">—</span>}
              </div>
              <div className="flex items-center gap-2 text-ink-soft">
                <ExternalLink size={13} className="shrink-0 text-ink-faint" />
                {supplier.site ? (
                  <a href={supplier.site.startsWith('http') ? supplier.site : `https://${supplier.site}`} target="_blank" rel="noreferrer" className="truncate hover:text-accent">
                    {supplier.site}
                  </a>
                ) : (
                  <span className="text-ink-faint">—</span>
                )}
              </div>
              <div className="flex items-center gap-2 text-ink-soft">
                <ShieldCheck size={13} className={`shrink-0 ${supplier.registry?.is_active === false ? 'text-danger' : 'text-ink-faint'}`} />
                {supplier.registry ? (
                  <span className={supplier.registry.is_active === false ? 'text-danger' : undefined}>
                    {supplier.registry.is_active === false ? 'Ликвидировано' : supplier.registry.status || 'Действует'}
                  </span>
                ) : (
                  <span className="text-ink-faint">ЕГРЮЛ не проверялся</span>
                )}
              </div>
              {supplier.registry && (
                <div className="flex items-center gap-2 text-ink-soft">
                  <Building2 size={13} className="shrink-0 text-ink-faint" />
                  ОГРН {supplier.registry.ogrn}
                  {checkoUrl(supplier.registry.ogrn) && (
                    <a
                      href={checkoUrl(supplier.registry.ogrn)!}
                      target="_blank"
                      rel="noreferrer"
                      title="Профиль на Checko"
                      className="flex h-5 w-5 items-center justify-center rounded hover:bg-surface-hover"
                    >
                      <img src={checkoIcon} alt="Checko" className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-border bg-surface">
            <h2 className="border-b border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink">История заявок</h2>
            {supplier.history.length === 0 ? (
              <EmptyState icon={MessageSquareText} title="Пока не участвовал в заявках" />
            ) : (
              <div className="divide-y divide-border">
                {supplier.history.map((h) => {
                  const meta = outcomeMeta[h.outcome] ?? outcomeMeta.not_sent;
                  return (
                    <button
                      key={`${h.request_id}-${h.supplier_id}`}
                      onClick={() => navigate(`/requests/${h.request_id}`)}
                      className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-surface-hover"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12.5px] font-medium text-ink">{h.request_title}</p>
                        <p className="text-[11px] text-ink-faint">{formatDateTime(h.date)}</p>
                      </div>
                      {h.rating != null && <span className="text-[11px] text-ink-faint">★ {h.rating}</span>}
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<MessageSquareText size={13} />}
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/messages?request=${h.request_id}&supplier=${h.supplier_id}`);
                        }}
                      >
                        Переписка
                      </Button>
                    </button>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-surface p-4">
            <h2 className="mb-3 text-[12.5px] font-semibold text-ink">Показатели</h2>
            <dl className="space-y-2.5 text-[12.5px]">
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Заявок</dt>
                <dd className="font-medium text-ink">{supplier.total_requests}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Отвечаемость</dt>
                <dd className="font-medium text-ink">{supplier.total_requests > 0 ? formatPercent(supplier.response_rate / 100) : '—'}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Среднее время ответа</dt>
                <dd className="font-medium text-ink">{supplier.avg_response_hours != null ? `~${supplier.avg_response_hours} ч` : '—'}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-ink-muted">Последний контакт</dt>
                <dd className="font-medium text-ink">{supplier.last_contact_at ? formatDateTime(supplier.last_contact_at) : 'Не было'}</dd>
              </div>
              {companyAge(supplier.registry?.registered_at) && (
                <div className="flex items-center justify-between">
                  <dt className="text-ink-muted">Возраст компании</dt>
                  <dd className="font-medium text-ink">{companyAge(supplier.registry?.registered_at)}</dd>
                </div>
              )}
              {supplier.finances && (
                <>
                  <div className="flex items-center justify-between">
                    <dt className="text-ink-muted">Выручка {supplier.finances.report_year ?? ''}</dt>
                    <dd className="font-medium text-ink">{formatMoney(supplier.finances.revenue)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="text-ink-muted">Прибыль {supplier.finances.report_year ?? ''}</dt>
                    <dd className="font-medium text-ink">{formatMoney(supplier.finances.profit)}</dd>
                  </div>
                </>
              )}
            </dl>
          </section>

          <section className="rounded-lg border border-border bg-surface p-4">
            <h2 className="mb-2 text-[12.5px] font-semibold text-ink">Заметка</h2>
            {noteLoaded && (
              <textarea
                value={note}
                onChange={(e) => handleNoteChange(e.target.value)}
                placeholder="Контекст по этому поставщику — виден только вам…"
                className="min-h-[100px] w-full resize-y rounded-md border border-border-strong bg-canvas px-3 py-2 text-[12.5px] leading-relaxed outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
              />
            )}
            <p className="mt-1.5 text-[11px] text-ink-faint">
              {noteSaveState === 'saving' ? 'Сохраняем…' : noteSaveState === 'saved' ? 'Сохранено' : ' '}
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
