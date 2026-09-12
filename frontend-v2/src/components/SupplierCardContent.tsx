import {
  Ban,
  Building2,
  Check,
  ExternalLink,
  Mail,
  MessageSquareText,
  Phone,
  Plus,
  Send,
  ShieldCheck,
  Star,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  Trash2,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import checkoIcon from '../assets/checko-icon.png';
import { FinanceTrend } from './FinanceTrend';
import { QuickAddTaskButton } from './QuickAddTaskButton';
import { Avatar } from './ui/Avatar';
import { Badge, type Tone } from './ui/Badge';
import { Button } from './ui/Button';
import { CopyButton } from './ui/CopyButton';
import { EmptyState } from './ui/EmptyState';
import { ErrorState, LoadingState } from './ui/ErrorState';
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

function StatCard({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'success' | 'danger' }) {
  return (
    <div className="rounded-md border border-border bg-canvas px-3 py-2.5">
      <p className="text-[10.5px] uppercase tracking-wide text-ink-faint">{label}</p>
      <p className={`mt-0.5 text-[17px] font-semibold leading-tight ${tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : 'text-ink'}`}>{value}</p>
      {sub && <p className="text-[10.5px] text-ink-faint">{sub}</p>}
    </div>
  );
}

/** The supplier profile: contacts, finances, history, favourite/blacklist
 * actions, and the supplier's own (global, cross-request) note. Shared by the
 * full `/suppliers/:id` page and the contextual panel opened from Messages
 * (`SupplierCardPanel`) -- one implementation so the two never drift apart.
 * `compact` drops the page's wide 3-column layout down to a single stacked
 * column that fits a ~400px side panel regardless of viewport width (the
 * page's `lg:grid-cols-3` only reacts to viewport, not container, width). */
export function SupplierCardContent({ supplierId, compact = false }: { supplierId: number; compact?: boolean }) {
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
  const age = companyAge(supplier.registry?.registered_at);
  const checko = checkoUrl(supplier.registry?.ogrn);
  const profit = supplier.finances?.profit ?? null;
  const latestThread = supplier.history.find((h) => h.outcome !== 'not_sent') ?? null;
  const latestRequestOnly = latestThread ? null : (supplier.history[0] ?? null);
  const hasCheckoRisks = (supplier.risks?.length ?? 0) > 0;

  return (
    <div className={compact ? 'space-y-4 px-3.5 py-3.5' : ''}>
      <div className={compact ? 'space-y-3' : 'flex flex-wrap items-start justify-between gap-4 px-4 sm:px-6 pb-4 pt-2'}>
        <div className="flex min-w-0 items-center gap-3">
          <Avatar name={supplier.name} size={compact ? 'md' : 'lg'} />
          <div className="min-w-0">
            <h1 className={compact ? 'truncate text-[15px] font-semibold leading-tight text-ink' : 'font-display text-[19px] font-semibold leading-tight text-ink'}>
              {formatCompanyName(supplier.name)}
            </h1>
            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[12px] text-ink-muted">
              {supplier.inn && (
                <>
                  ИНН {supplier.inn}
                  <CopyButton text={supplier.inn} />
                </>
              )}
              {supplier.registry && (
                <span className={`flex items-center gap-1 ${supplier.registry.is_active === false ? 'text-danger' : 'text-success'}`}>
                  <ShieldCheck size={12} />
                  {supplier.registry.is_active === false ? 'Ликвидировано' : supplier.registry.status || 'Действует'}
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isBlacklisted && <Badge tone="danger">В чёрном списке</Badge>}
          {isFavorite && <Badge tone="accent">Избранный</Badge>}
          {latestThread ? (
            <Button
              variant="primary"
              size="sm"
              icon={<Send size={13} />}
              onClick={() => navigate(`/messages?request=${latestThread.request_id}&supplier=${latestThread.supplier_id}`)}
            >
              Написать
            </Button>
          ) : (
            latestRequestOnly && (
              <Button
                variant="primary"
                size="sm"
                icon={<Send size={13} />}
                title="Письмо ещё не отправлялось — выберите поставщика в заявке, чтобы написать"
                onClick={() => navigate(`/requests/${latestRequestOnly.request_id}`)}
              >
                Написать
              </Button>
            )
          )}
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
        <div className={compact ? 'rounded-md border border-border bg-surface-hover p-3' : 'mx-4 mb-4 rounded-md border border-border bg-surface-hover p-3 sm:mx-6'}>
          <label className="mb-1 block text-[12px] font-medium text-ink-soft">Причина (обязательно для чёрного списка)</label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              autoFocus
              value={blacklistReason}
              onChange={(e) => setBlacklistReason(e.target.value)}
              placeholder="Например: не отвечает на запросы, срывает сроки…"
              className="h-9 w-full min-w-0 flex-1 rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border sm:w-auto"
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
      {relationshipError && <p className={compact ? 'text-[12px] text-danger' : 'mx-4 mb-3 text-[12px] text-danger sm:mx-6'}>{relationshipError}</p>}

      <div className={compact ? 'space-y-4' : 'grid grid-cols-1 gap-4 px-4 sm:px-6 pb-6 lg:grid-cols-3'}>
        <div className={compact ? 'space-y-4' : 'space-y-4 lg:col-span-2'}>
          <section className="rounded-lg border border-border bg-surface">
            <h2 className="border-b border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink">Контакты и реквизиты</h2>
            <div className={compact ? 'space-y-3 p-4 text-[12.5px]' : 'grid grid-cols-1 gap-3 p-4 text-[12.5px] sm:grid-cols-2'}>
              <div className="flex items-center gap-1.5 text-ink-soft">
                <Mail size={13} className="shrink-0 text-ink-faint" />
                {supplier.email ? (
                  <>
                    <a href={`mailto:${supplier.email}`} className="truncate hover:text-accent">
                      {supplier.email}
                    </a>
                    <CopyButton text={supplier.email} />
                  </>
                ) : (
                  <span className="text-ink-faint">—</span>
                )}
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
              {supplier.registry && (
                <div className="flex items-center gap-2 text-ink-soft">
                  <Building2 size={13} className="shrink-0 text-ink-faint" />
                  ОГРН {supplier.registry.ogrn}
                  {checko && (
                    <a href={checko} target="_blank" rel="noreferrer" title="Профиль на Checko" className="flex h-5 w-5 items-center justify-center rounded hover:bg-surface-hover">
                      <img src={checkoIcon} alt="Checko" className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>
              )}
            </div>
          </section>

          <SupplierContacts supplierId={supplier.id} contacts={supplier.contacts} onChanged={state.reload} />
          <SupplierClassifications supplierId={supplier.id} classifications={supplier.classifications} onChanged={state.reload} />

          {supplier.finance_history.length >= 2 && (
            <section className="rounded-lg border border-border bg-surface p-4">
              <FinanceTrend years={supplier.finance_history} />
            </section>
          )}

          {!compact && (
            <section className="rounded-lg border border-border bg-surface">
              <h2 className="border-b border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink">История заявок</h2>
              {supplier.history.length === 0 ? (
                <EmptyState icon={MessageSquareText} title="Пока не участвовал в заявках" />
              ) : (
                <div className="divide-y divide-border">
                  {supplier.history.map((h) => {
                    const meta = outcomeMeta[h.outcome] ?? outcomeMeta.not_sent;
                    return (
                      <div
                        key={`${h.request_id}-${h.supplier_id}`}
                        onClick={() => navigate(`/requests/${h.request_id}`)}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            navigate(`/requests/${h.request_id}`);
                          }
                        }}
                        role="link"
                        tabIndex={0}
                        className="flex w-full cursor-pointer flex-wrap items-center gap-x-3 gap-y-1.5 px-4 py-2.5 text-left hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
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
                          <span className="hidden sm:inline">Переписка</span>
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          )}
        </div>

        <div className="space-y-4">
          <section className="rounded-lg border border-border bg-surface p-4">
            <h2 className="mb-3 text-[12.5px] font-semibold text-ink">Показатели</h2>
            <div className="grid grid-cols-2 gap-2.5">
              <StatCard label="Возраст" value={age ?? '—'} />
              <StatCard label="Заявок" value={String(supplier.total_requests)} />
              <StatCard
                label="Выручка"
                value={supplier.finances?.revenue != null ? formatMoney(supplier.finances.revenue) : '—'}
                sub={supplier.finances?.report_year ? `за ${supplier.finances.report_year}` : undefined}
              />
              <StatCard
                label="Прибыль"
                value={profit != null ? formatMoney(profit) : '—'}
                tone={profit != null ? (profit >= 0 ? 'success' : 'danger') : undefined}
              />
              <StatCard label="Отклик" value={supplier.total_requests > 0 ? formatPercent(supplier.response_rate / 100) : '—'} tone={supplier.response_rate >= 50 ? 'success' : undefined} />
              <StatCard label="Ср. время ответа" value={supplier.avg_response_hours != null ? `~${supplier.avg_response_hours} ч` : '—'} />
            </div>
            <div className="mt-2.5 flex items-center justify-between rounded-md border border-border bg-canvas px-3 py-2 text-[12px]">
              <span className="text-ink-muted">Последний контакт</span>
              <span className="font-medium text-ink">{supplier.last_contact_at ? formatDateTime(supplier.last_contact_at) : 'Не было'}</span>
            </div>
            {profit != null && (
              <p className="mt-1.5 flex items-center gap-1 text-[11px] text-ink-faint">
                {profit >= 0 ? <TrendingUp size={11} className="text-success" /> : <TrendingDown size={11} className="text-danger" />}
                {profit >= 0 ? 'Прибыльная компания по последней отчётности' : 'Убыток по последней отчётности'}
              </p>
            )}
          </section>

          <section className={`rounded-lg border p-4 ${hasCheckoRisks ? 'border-danger-border bg-danger-subtle/40' : 'border-border bg-surface'}`}>
              <h2 className="flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
                {hasCheckoRisks ? <TriangleAlert size={14} className="text-danger" /> : <ShieldCheck size={14} className={supplier.risks === null ? 'text-ink-muted' : 'text-success'} />}
                Проверка Checko
              </h2>
              {hasCheckoRisks ? (
                <ul className="mt-2 space-y-1.5">
                  {supplier.risks?.map((risk) => (
                    <li key={risk} className="flex gap-1.5 text-[11.5px] leading-snug text-danger">
                      <span aria-hidden="true">•</span>
                      <span>{risk}</span>
                    </li>
                  ))}
                </ul>
              ) : supplier.risks === null ? (
                <p className="mt-1.5 text-[11.5px] leading-snug text-ink-muted">Риски по Checko ещё не проверены для этого поставщика.</p>
              ) : (
                <p className="mt-1.5 text-[11.5px] leading-snug text-ink-muted">В текущих данных Checko нет отмеченных факторов риска.</p>
              )}
              <p className="mt-2 text-[10.5px] text-ink-faint">Сведения из публичного реестра; проверяйте их актуальность перед важной сделкой.</p>
          </section>

          <section className="rounded-lg border border-border bg-surface p-4">
            <h2 className="mb-2 text-[12.5px] font-semibold text-ink">Заметка о поставщике</h2>
            {noteLoaded && (
              <textarea
                value={note}
                onChange={(e) => handleNoteChange(e.target.value)}
                placeholder="Контекст по этому поставщику — виден только вам…"
                className="min-h-[100px] w-full resize-y rounded-md border border-border-strong bg-canvas px-3 py-2 text-[12.5px] leading-relaxed outline-none placeholder:text-ink-faint focus:border-accent focus:ring-1 focus:ring-accent-border"
              />
            )}
            <p className="mt-1.5 text-[11px] text-ink-faint">
              {noteSaveState === 'saving' ? 'Сохраняем…' : noteSaveState === 'saved' ? 'Сохранено' : ' '}
            </p>
          </section>

          {compact && supplier.history.length > 0 && (
            <section className="rounded-lg border border-border bg-surface">
              <h2 className="border-b border-border px-4 py-2.5 text-[12.5px] font-semibold text-ink">История заявок</h2>
              <div className="divide-y divide-border">
                {supplier.history.map((h) => {
                  const meta = outcomeMeta[h.outcome] ?? outcomeMeta.not_sent;
                  return (
                    <button
                      key={`${h.request_id}-${h.supplier_id}`}
                      onClick={() => navigate(`/requests/${h.request_id}`)}
                      className="flex w-full flex-col gap-1 px-4 py-2.5 text-left hover:bg-surface-hover"
                    >
                      <p className="truncate text-[12px] font-medium text-ink">{h.request_title}</p>
                      <div className="flex items-center gap-2">
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                        <span className="text-[10.5px] text-ink-faint">{formatDateTime(h.date)}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function SupplierContacts({ supplierId, contacts, onChanged }: { supplierId: number; contacts: import('../lib/types').WorkspaceSupplierContact[]; onChanged: () => void }) {
  const empty: { name: string; role: string; phone: string; email: string; visibility: 'private' | 'workspace' } = { name: '', role: '', phone: '', email: '', visibility: 'private' };
  const [draft, setDraft] = useState(empty);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const editing = contacts.find((contact) => contact.id === editingId) ?? null;

  function beginEdit(contact: import('../lib/types').WorkspaceSupplierContact) {
    setEditingId(contact.id);
    setDraft({ name: contact.name, role: contact.role, phone: contact.phone, email: contact.email, visibility: contact.visibility });
    setError('');
    setOpen(true);
  }

  async function save() {
    if (!draft.name.trim()) return;
    setBusy(true);
    setError('');
    try {
      if (editing) await api.updateWorkspaceSupplierContact(supplierId, editing.id, draft);
      else await api.createWorkspaceSupplierContact(supplierId, draft);
      setDraft(empty); setEditingId(null); setOpen(false); onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось сохранить контакт.');
    } finally { setBusy(false); }
  }

  async function remove(contactId: number) {
    setBusy(true); setError('');
    try { await api.deleteWorkspaceSupplierContact(supplierId, contactId); onChanged(); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Не удалось удалить контакт.'); }
    finally { setBusy(false); }
  }

  return <section aria-label="Классификация поставщика" className="rounded-lg border border-border bg-surface">
    <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
      <div><h2 className="text-[12.5px] font-semibold text-ink">Контактные лица</h2><p className="text-[10.5px] text-ink-faint">Личные или для команды; не публикуются в карточке компании.</p></div>
      <Button variant="secondary" size="sm" icon={<Plus size={13} />} onClick={() => { setEditingId(null); setDraft(empty); setError(''); setOpen((value) => !value); }}>Контакт</Button>
    </header>
    {contacts.length === 0 && !open && <p className="px-4 py-3 text-[12px] text-ink-faint">Контактных лиц пока нет.</p>}
    {contacts.length > 0 && <div className="divide-y divide-border">{contacts.map((contact) => <div key={contact.id} className="flex items-start gap-3 px-4 py-3">
      <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-1.5"><p className="font-medium text-[12.5px] text-ink">{contact.name}</p><Badge tone="neutral">{contact.visibility === 'private' ? 'Личный' : 'Команда'}</Badge></div>
      {contact.role && <p className="mt-0.5 text-[11.5px] text-ink-muted">{contact.role}</p>}<div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-ink-soft">{contact.email && <a href={`mailto:${contact.email}`} className="hover:text-accent">{contact.email}</a>}{contact.phone && <a href={`tel:${contact.phone}`} className="hover:text-accent">{contact.phone}</a>}</div></div>
      <div className="flex shrink-0 gap-1"><button type="button" onClick={() => beginEdit(contact)} className="rounded px-2 py-1 text-[11px] text-ink-muted hover:bg-surface-hover">Изменить</button><button type="button" onClick={() => void remove(contact.id)} disabled={busy} aria-label="Удалить контакт" className="flex h-7 w-7 items-center justify-center rounded text-ink-faint hover:bg-danger-subtle hover:text-danger disabled:opacity-50"><Trash2 size={13} /></button></div>
    </div>)}</div>}
    {open && <div className="grid gap-2 border-t border-border p-4 sm:grid-cols-2"><input autoFocus value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Имя *" aria-label="Имя контактного лица" className="h-8 rounded-md border border-border-strong bg-canvas px-2.5 text-[12px] outline-none focus:border-accent" /><input value={draft.role} onChange={(e) => setDraft({ ...draft, role: e.target.value })} placeholder="Роль" aria-label="Роль контактного лица" className="h-8 rounded-md border border-border-strong bg-canvas px-2.5 text-[12px] outline-none focus:border-accent" /><input value={draft.phone} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} placeholder="Телефон" aria-label="Телефон контактного лица" inputMode="tel" className="h-8 rounded-md border border-border-strong bg-canvas px-2.5 text-[12px] outline-none focus:border-accent" /><input value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} placeholder="Email" aria-label="Email контактного лица" className="h-8 rounded-md border border-border-strong bg-canvas px-2.5 text-[12px] outline-none focus:border-accent" /><select value={draft.visibility} onChange={(e) => setDraft({ ...draft, visibility: e.target.value as 'private' | 'workspace' })} aria-label="Видимость контакта" className="h-8 rounded-md border border-border-strong bg-canvas px-2 text-[12px] outline-none focus:border-accent"><option value="private">Только я</option><option value="workspace">Для команды</option></select><div className="flex justify-end gap-2"><Button variant="secondary" size="sm" onClick={() => { setOpen(false); setEditingId(null); }}>Отмена</Button><Button variant="primary" size="sm" disabled={!draft.name.trim() || busy} onClick={() => void save()}>{editing ? 'Сохранить' : 'Добавить'}</Button></div>{error && <p className="text-[11.5px] text-danger sm:col-span-2">{error}</p>}</div>}
  </section>;
}

const classificationLabels = { category: 'Категория', product: 'Товар', brand: 'Бренд', specialization: 'Специализация' } as const;
const classificationSourceLabels = { manual: 'Вручную', registry: 'Реестр', ai: 'AI' } as const;

function SupplierClassifications({ supplierId, classifications, onChanged }: { supplierId: number; classifications: import('../lib/types').WorkspaceSupplierClassification[]; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'category' | 'product' | 'brand' | 'specialization'>('category');
  const [value, setValue] = useState('');
  const [confidence, setConfidence] = useState<'low' | 'medium' | 'high'>('medium');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function add() {
    if (!value.trim()) return;
    setBusy(true); setError('');
    try {
      await api.createWorkspaceSupplierClassification(supplierId, { kind, value, confidence });
      setValue(''); setOpen(false); onChanged();
    } catch (e) { setError(e instanceof ApiError ? e.message : 'Не удалось сохранить классификацию.'); }
    finally { setBusy(false); }
  }
  async function remove(id: number) {
    setBusy(true); setError('');
    try { await api.deleteWorkspaceSupplierClassification(supplierId, id); onChanged(); }
    catch (e) { setError(e instanceof ApiError ? e.message : 'Не удалось удалить классификацию.'); }
    finally { setBusy(false); }
  }

  return <section className="rounded-lg border border-border bg-surface">
    <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
      <div><h2 className="text-[12.5px] font-semibold text-ink">Классификация</h2><p className="text-[10.5px] text-ink-faint">Рабочие метки с источником и уровнем уверенности.</p></div>
      <Button variant="secondary" size="sm" icon={<Plus size={13} />} onClick={() => { setError(''); setOpen((current) => !current); }}>Метка</Button>
    </header>
    {classifications.length === 0 && !open && <p className="px-4 py-3 text-[12px] text-ink-faint">Категории, товары и бренды пока не добавлены.</p>}
    {classifications.length > 0 && <div className="divide-y divide-border">{classifications.map((item) => <div key={item.id} className="flex items-start gap-3 px-4 py-2.5"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-1.5"><Badge tone="accent">{classificationLabels[item.kind]}</Badge><p className="truncate text-[12.5px] font-medium text-ink">{item.value}</p></div><p className="mt-1 text-[10.5px] text-ink-faint">{classificationSourceLabels[item.source]} · уверенность: {item.confidence === 'high' ? 'высокая' : item.confidence === 'low' ? 'низкая' : 'средняя'}</p></div><button type="button" onClick={() => void remove(item.id)} disabled={busy} aria-label={`Удалить метку ${item.value}`} className="flex h-7 w-7 shrink-0 items-center justify-center rounded text-ink-faint hover:bg-danger-subtle hover:text-danger disabled:opacity-50"><Trash2 size={13} /></button></div>)}</div>}
    {open && <div className="grid gap-2 border-t border-border p-4 sm:grid-cols-2"><select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)} aria-label="Тип классификации" className="h-8 rounded-md border border-border-strong bg-canvas px-2 text-[12px] outline-none focus:border-accent">{Object.entries(classificationLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><input autoFocus value={value} onChange={(e) => setValue(e.target.value)} placeholder="Например, печи-камины" aria-label="Значение классификации" className="h-8 rounded-md border border-border-strong bg-canvas px-2.5 text-[12px] outline-none focus:border-accent"/><select value={confidence} onChange={(e) => setConfidence(e.target.value as typeof confidence)} aria-label="Уверенность классификации" className="h-8 rounded-md border border-border-strong bg-canvas px-2 text-[12px] outline-none focus:border-accent"><option value="high">Высокая уверенность</option><option value="medium">Средняя уверенность</option><option value="low">Низкая уверенность</option></select><div className="flex justify-end gap-2"><Button variant="secondary" size="sm" onClick={() => setOpen(false)}>Отмена</Button><Button variant="primary" size="sm" disabled={!value.trim() || busy} onClick={() => void add()}>Добавить</Button></div>{error && <p className="text-[11.5px] text-danger sm:col-span-2">{error}</p>}<p className="text-[10.5px] text-ink-faint sm:col-span-2">Ручная метка всегда хранится с источником «Вручную». Источник «Реестр» или «AI» появится только при отдельной подтверждённой интеграции.</p></div>}
  </section>;
}
