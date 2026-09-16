import { AlertTriangle, Bell, Check, ExternalLink, FolderSearch, Loader2, Mail, MailWarning, RefreshCw, Send, ShieldCheck, Trash2, Volume2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { useAuth } from '../lib/AuthContext';
import { formatDateTime, formatRelativeTime } from '../lib/format';
import { useReminders } from '../lib/RemindersContext';
import type { MailAccount } from '../lib/types';
import { useApiData } from '../lib/useApiData';

function ToggleRow({ icon, label, checked, onChange, hint }: { icon: ReactNode; label: string; checked: boolean; onChange: (value: boolean) => void; hint?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        {icon}
        <div className="min-w-0">
          <p className="text-[12.5px] font-medium text-ink">{label}</p>
          {hint && <p className="truncate text-[11px] text-ink-faint">{hint}</p>}
        </div>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-surface-hover border border-border-strong'}`}
      >
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-4' : 'translate-x-0.5'}`} />
      </button>
    </div>
  );
}

/** §13 of the reminder spec: real, persisted (not localStorage-only) sound
 * and browser-notification preferences. Browser permission itself is only
 * requested on an explicit click here -- never automatically. */
function NotificationSettingsCard() {
  const { settings, updateSettings } = useReminders();
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
  );
  const [error, setError] = useState('');

  async function toggleSound(value: boolean) {
    setError('');
    try {
      await updateSettings({ ...settings, sound_enabled: value });
    } catch {
      setError('Не удалось сохранить настройку звука.');
    }
  }

  async function toggleBrowserNotifications(value: boolean) {
    setError('');
    if (value && permission !== 'granted') {
      if (permission === 'unsupported') {
        setError('Браузер не поддерживает системные уведомления.');
        return;
      }
      try {
        const result = await Notification.requestPermission();
        setPermission(result);
        if (result !== 'granted') return;
      } catch {
        setError('Не удалось запросить разрешение на уведомления.');
        return;
      }
    }
    try {
      await updateSettings({ ...settings, browser_notifications_enabled: value });
    } catch {
      setError('Не удалось сохранить настройку уведомлений.');
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2">
        <Bell size={15} className="text-ink-muted" />
        <h2 className="text-[13px] font-semibold text-ink">Уведомления</h2>
      </div>
      <div className="mt-1 divide-y divide-border">
        <ToggleRow icon={<Volume2 size={14} className="shrink-0 text-ink-faint" />} label="Звуковые уведомления" checked={settings.sound_enabled} onChange={toggleSound} />
        <ToggleRow
          icon={<Bell size={14} className="shrink-0 text-ink-faint" />}
          label="Системные уведомления"
          checked={settings.browser_notifications_enabled && permission === 'granted'}
          onChange={toggleBrowserNotifications}
          hint={permission === 'denied' ? 'Разрешение заблокировано в настройках браузера' : undefined}
        />
      </div>
      {error && <p className="mt-2 text-[11.5px] text-danger">{error}</p>}
    </div>
  );
}

/** Global kill switch for real outgoing mail (POST /api/mail/runtime/outgoing).
 * Owner-only on the backend (mail/service.py::set_outgoing_enabled) and
 * requires an explicit confirmation flag -- this control is the only UI
 * surface for it anywhere in the app, so a non-owner click fails with a
 * clear permission error rather than silently doing nothing. */
function OutgoingMailControl() {
  const state = useApiData(() => api.outgoingMailStatus(), []);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function apply(enabled: boolean) {
    setBusy(true);
    setMessage('');
    try {
      await api.setOutgoingMailEnabled(enabled);
      setConfirming(false);
      state.reload();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось изменить настройку.');
    } finally {
      setBusy(false);
    }
  }

  if (state.status === 'loading') return null;
  if (state.status === 'error') {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <h2 className="text-[13px] font-semibold text-ink">Исходящая почта</h2>
        <p className="mt-2 text-[12px] text-danger">{state.message}</p>
      </div>
    );
  }

  const { durable_outgoing_enabled: durable, effective_outgoing_enabled: effective, queued_backlog: backlog } = state.data;
  const hasBacklog = !!backlog && backlog.count > 0;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-2">
        {effective ? <Send size={15} className="text-success" /> : <MailWarning size={15} className="text-ink-muted" />}
        <h2 className="text-[13px] font-semibold text-ink">Исходящая почта</h2>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium ${effective ? 'bg-success-subtle text-success' : 'bg-surface-hover text-ink-muted'}`}>
          {effective ? 'Включена' : 'Отключена'}
        </span>
      </div>
      <p className="mt-1.5 text-[12px] text-ink-muted">
        {effective
          ? 'Письма поставщикам уходят по-настоящему с подключённых аккаунтов.'
          : 'Письма поставщикам не отправляются, пока это выключено.'}
      </p>
      {durable && !effective && (
        <p className="mt-1.5 text-[11.5px] text-warning">
          Переключатель включён, но сервер всё равно блокирует отправку (не production-окружение, не пройдена проверка канонической базы или не занят live-mail lock).
        </p>
      )}
      {hasBacklog && (
        <p className="mt-1.5 flex items-start gap-1.5 text-[11.5px] text-warning">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          В очереди {backlog.count} {backlog.count === 1 ? 'письмо ждёт' : 'писем ждут'} отправки
          {backlog.oldest_created_at && <> (самое старое — {formatRelativeTime(backlog.oldest_created_at)})</>}
          {!durable && '. Как только вы включите исходящую почту, они уйдут сразу же, не только новое письмо.'}
        </p>
      )}
      {message && <p className="mt-1.5 text-[11.5px] text-danger">{message}</p>}

      {!confirming ? (
        <Button
          variant={durable ? 'ghost' : 'primary'}
          size="sm"
          className="mt-3"
          icon={<Send size={13} />}
          onClick={() => setConfirming(true)}
        >
          {durable ? 'Отключить' : 'Включить'}
        </Button>
      ) : (
        <div className="mt-3 rounded-md border border-warning-border bg-warning-subtle px-3 py-2.5">
          <p className="flex items-start gap-2 text-[12px] text-warning">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            {durable
              ? 'Отключить исходящую почту для всех аккаунтов?'
              : hasBacklog
                ? `Включить реальную отправку? В очереди уже ${backlog.count} ${backlog.count === 1 ? 'письмо' : 'писем'} — они уйдут немедленно вместе с новыми.`
                : 'Включить реальную отправку писем поставщикам со всех подключённых аккаунтов?'}
          </p>
          <div className="mt-2.5 flex items-center gap-2">
            <Button variant="primary" size="sm" disabled={busy} onClick={() => void apply(!durable)}>
              {busy ? 'Применяю…' : durable ? 'Да, отключить' : 'Да, включить'}
            </Button>
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirming(false)}>
              Отмена
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

const MAIL_ERROR_LABELS: Record<string, string> = {
  not_configured: 'Подключение Яндекс.Почты не настроено на сервере.',
  access_denied: 'В доступе к почте отказано.',
  missing_code: 'Яндекс не вернул код авторизации — попробуйте ещё раз.',
  connection_failed: 'Не удалось завершить подключение. Попробуйте ещё раз.',
};

function incomingHealthLabel(a: MailAccount): { label: string; tone: 'success' | 'danger' | 'warning' | 'neutral' } {
  const health = a.incoming_health ?? (a.incoming_last_error ? 'error' : a.incoming_enabled ? 'pending' : 'disabled');
  if (health === 'healthy') return { label: 'Работают', tone: 'success' };
  if (health === 'error') return { label: 'Ошибка синхронизации', tone: 'danger' };
  if (health === 'disabled') return { label: 'Отключены', tone: 'neutral' };
  return { label: 'Проверка нужна', tone: 'warning' };
}

function StatusPill({ label, tone }: { label: string; tone: 'success' | 'danger' | 'warning' | 'neutral' }) {
  const cls =
    tone === 'success'
      ? 'bg-success-subtle text-success'
      : tone === 'danger'
        ? 'bg-danger-subtle text-danger'
        : tone === 'warning'
          ? 'bg-warning-subtle text-warning'
          : 'bg-surface-hover text-ink-muted';
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${cls}`}>{label}</span>;
}

function MiniStat({ label, value, tone = 'neutral' }: { label: string; value: string; tone?: 'success' | 'danger' | 'warning' | 'neutral' }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-ink-faint">{label}</p>
      <StatusPill label={value} tone={tone} />
    </div>
  );
}

function AccountCard({ account, onChanged }: { account: MailAccount; onChanged: () => void }) {
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [previewingSent, setPreviewingSent] = useState(false);
  const [syncingSent, setSyncingSent] = useState(false);
  const [updatingSentAutomation, setUpdatingSentAutomation] = useState(false);
  const syncingSentRef = useRef(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [message, setMessage] = useState('');
  const [sentPreview, setSentPreview] = useState<{ folder: string; marked_count: number } | null>(null);

  const incoming = incomingHealthLabel(account);
  const outgoingTone: 'success' | 'danger' | 'warning' = account.outgoing_health === 'error' ? 'danger' : account.outgoing_enabled ? 'success' : 'warning';
  const outgoingLabel = account.outgoing_health === 'error' ? 'Ошибка подключения' : account.outgoing_enabled ? 'Готовы' : 'Отключены';
  const incomingError = account.incoming_last_error || (incoming.tone === 'danger' ? account.last_error : null);

  async function handleTest() {
    setTesting(true);
    setMessage('');
    try {
      const res = await api.mailTest(account.id);
      setMessage(res.message || 'Проверено.');
      onChanged();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось проверить подключение.');
    } finally {
      setTesting(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    setMessage('');
    try {
      await api.mailSync(account.id);
      onChanged();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось синхронизировать входящие.');
    } finally {
      setSyncing(false);
    }
  }

  async function handleSentPreview() {
    setPreviewingSent(true);
    setMessage('');
    try {
      const preview = await api.mailSentPreview(account.id);
      setSentPreview(preview);
      setMessage(preview.marked_count
        ? `Найдено писем с SD-ID: ${preview.marked_count}. Импорт будет ограничен 25 письмами.`
        : 'В «Отправленных» нет писем с SD-ID. Личные письма не читались.');
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось проверить отправленные.');
    } finally {
      setPreviewingSent(false);
    }
  }

  async function handleSentSync() {
    if (syncingSentRef.current) return;
    syncingSentRef.current = true;
    setSyncingSent(true);
    setMessage('');
    try {
      const result = await api.mailSentSync(account.id);
      setSentPreview(null);
      setMessage(`Связано с заявками: ${result.linked}. В истории переписки: ${result.history_imported}.`);
      onChanged();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось импортировать отправленные.');
    } finally {
      syncingSentRef.current = false;
      setSyncingSent(false);
    }
  }

  async function handleSentAutomation() {
    const enabled = !account.sent_sync_enabled;
    setUpdatingSentAutomation(true);
    setMessage('');
    try {
      await api.setMailSentSyncEnabled(account.id, enabled);
      setMessage(enabled
        ? 'Автопоиск SD-писем включён: раз в 5 минут будут читаться только письма с [SD-…] в теме.'
        : 'Автопоиск SD-писем выключен. Ручной поиск в карточке заявки остаётся доступен.');
      onChanged();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось изменить автопоиск отправленных.');
    } finally {
      setUpdatingSentAutomation(false);
    }
  }

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      await api.mailDisconnectAccount(account.id);
      onChanged();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : 'Не удалось отключить аккаунт.');
      setDisconnecting(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13.5px] font-medium text-ink">{account.email}</p>
          <p className="text-[11.5px] text-ink-muted">
            {account.provider === 'mailru' ? 'Mail.ru' : 'Яндекс.Почта'} · {account.auth_mode === 'app_password' ? 'пароль приложения' : 'OAuth'}
          </p>
        </div>
        <StatusPill label={account.connected ? 'Подключён' : 'Нужна проверка'} tone={account.connected ? 'success' : 'warning'} />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
        <MiniStat label="Аккаунт" value={account.connected ? 'Подключён' : 'Нужна проверка'} tone={account.connected ? 'success' : 'warning'} />
        <MiniStat label="Исходящие" value={outgoingLabel} tone={outgoingTone} />
        <MiniStat label="Входящие ответы" value={incoming.label} tone={incoming.tone} />
      </div>

      <p className="mt-2.5 text-[11px] text-ink-faint">
        Последняя проверка: {account.incoming_last_success_at ? formatDateTime(account.incoming_last_success_at) : 'не проверялась'}
      </p>
      <div className="mt-2.5 flex items-center justify-between gap-3 rounded-md bg-canvas px-2.5 py-2">
        <div className="min-w-0">
          <p className="text-[11.5px] font-medium text-ink">Автопоиск SD-писем</p>
          <p className="text-[10.5px] text-ink-muted">Только «Отправленные» с <code>[SD-…]</code>; личные темы не читаются.</p>
        </div>
        <Button
          variant={account.sent_sync_enabled ? 'secondary' : 'ghost'}
          size="sm"
          icon={updatingSentAutomation ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          disabled={updatingSentAutomation}
          aria-pressed={account.sent_sync_enabled}
          onClick={() => void handleSentAutomation()}
        >
          {account.sent_sync_enabled ? 'Включён' : 'Выключен'}
        </Button>
      </div>
      {incomingError && <p className="mt-1 text-[11px] font-medium text-danger">Ошибка входящих: {incomingError}</p>}
      {message && <p className="mt-1.5 text-[11.5px] text-ink-soft">{message}</p>}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="secondary" size="sm" icon={testing ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />} disabled={testing} onClick={() => void handleTest()}>
          Проверить
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          disabled={syncing}
          onClick={() => void handleSync()}
        >
          {incoming.tone === 'danger' ? 'Повторить входящие' : 'Синхронизировать входящие'}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          icon={previewingSent ? <Loader2 size={13} className="animate-spin" /> : <FolderSearch size={13} />}
          disabled={previewingSent || syncingSent}
          onClick={() => void handleSentPreview()}
        >
          Найти в отправленных
        </Button>
        {sentPreview && sentPreview.marked_count > 0 && (
          <Button
            variant="primary"
            size="sm"
            icon={syncingSent ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            disabled={syncingSent}
            onClick={() => void handleSentSync()}
          >
            Импортировать SD-письма
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          className="sm:ml-auto text-danger hover:bg-danger-subtle"
          icon={<Trash2 size={13} />}
          disabled={disconnecting}
          onClick={() => void handleDisconnect()}
        >
          Отключить
        </Button>
      </div>
      <p className="mt-2 text-[11px] text-ink-faint">
        Поиск в «Отправленных» читает только темы с меткой <code>[SD-…]</code> и ничего не меняет; импорт появится только после просмотра результата.
      </p>
    </div>
  );
}

/** Which deployment this page is actually talking to -- local dev and the
 * deployed Vercel site both say "SupplyDesk" with nothing else
 * distinguishing them, which caused real confusion this session about
 * whether the outgoing-mail switch shown here was the local or the deployed
 * one. `runtime.environment` alone can't tell them apart: local dev is
 * deliberately configured with `SUPPLYDESK_ENV=production` too (that's what
 * lets a real send be tested from a laptop), so the database engine --
 * always SQLite locally, always Postgres on Vercel -- is the only reliable
 * signal for *which deployment*, not the safety-gate "environment" concept.
 * See ai/DEFERRED_FINDINGS.md FINDING-029. */
function RuntimeBadge() {
  const { runtime } = useAuth();
  if (!runtime) return null;
  const isDeployed = runtime.database === 'postgres';
  return (
    <Badge tone={isDeployed ? 'danger' : 'neutral'} dot>
      {isDeployed ? 'Облако (Vercel)' : 'Эта машина (локально)'}
    </Badge>
  );
}

export function Settings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const state = useApiData(() => api.mailStatus(), []);
  const [banner, setBanner] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const [mailruEmail, setMailruEmail] = useState('');
  const [mailruPassword, setMailruPassword] = useState('');
  const [mailruConnecting, setMailruConnecting] = useState(false);
  const [mailruError, setMailruError] = useState('');
  const [mailruMessage, setMailruMessage] = useState('');

  useEffect(() => {
    if (searchParams.get('connected') === 'true') {
      setBanner({ tone: 'success', text: 'Почта подключена.' });
      setSearchParams({}, { replace: true });
    } else if (searchParams.get('mail_error')) {
      const code = searchParams.get('mail_error') ?? '';
      setBanner({ tone: 'danger', text: MAIL_ERROR_LABELS[code] || 'Не удалось подключить почту.' });
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleMailruConnect() {
    if (!mailruEmail.trim() || !mailruPassword) {
      setMailruError('Укажите email Mail.ru и пароль приложения.');
      return;
    }
    setMailruConnecting(true);
    setMailruError('');
    setMailruMessage('');
    try {
      await api.mailConnectMailru(mailruEmail.trim(), mailruPassword);
      setMailruPassword('');
      setMailruMessage('Mail.ru подключён. Пароль приложения больше не хранится в форме.');
      state.reload();
    } catch (e) {
      setMailruError(e instanceof ApiError ? e.message : 'Не удалось подключить Mail.ru. Проверьте email и пароль приложения.');
    } finally {
      setMailruConnecting(false);
    }
  }

  if (state.status === 'loading') {
    return (
      <div className="flex h-full flex-col overflow-auto">
        <PageHeader title="Настройки" actions={<RuntimeBadge />} />
        <LoadingState label="Загружаем настройки почты…" />
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className="flex h-full flex-col overflow-auto">
        <PageHeader title="Настройки" actions={<RuntimeBadge />} />
        <ErrorState message={state.message} onRetry={state.reload} />
      </div>
    );
  }

  const accounts = state.data.accounts;
  const hasConnectedYandex = accounts.some((a) => a.provider === 'yandex' && a.connected);

  return (
    <div className="flex h-full flex-col overflow-auto">
      <PageHeader title="Настройки" description="Почтовые аккаунты для отправки и приёма писем поставщиков" actions={<RuntimeBadge />} />

      <div className="max-w-2xl space-y-4 px-4 sm:px-6 pb-6">
        {banner && (
          <div
            className={`flex items-center gap-2 rounded-md border px-3 py-2 text-[12.5px] ${
              banner.tone === 'success' ? 'border-success-border bg-success-subtle text-success' : 'border-danger-border bg-danger-subtle text-danger'
            }`}
          >
            {banner.tone === 'success' ? <Check size={14} /> : <AlertTriangle size={14} />}
            {banner.text}
          </div>
        )}

        <NotificationSettingsCard />

        <OutgoingMailControl />

        {accounts.length > 0 && (
          <div className="space-y-3">
            {accounts.map((a) => (
              <AccountCard key={a.id} account={a} onChanged={() => state.reload()} />
            ))}
          </div>
        )}

        {!hasConnectedYandex && (
          <div className="rounded-lg border border-border bg-surface p-4">
            <h2 className="text-[13px] font-semibold text-ink">Подключить Яндекс.Почту</h2>
            <p className="mt-1 text-[12px] text-ink-muted">Вход и разрешение на отправку/приём писем через OAuth Яндекса.</p>
            <Button
              variant="primary"
              size="sm"
              className="mt-3"
              icon={<Mail size={13} />}
              onClick={() => {
                window.location.href = '/api/mail/yandex/start';
              }}
            >
              Подключить Яндекс.Почту
            </Button>
          </div>
        )}

        <div className="rounded-lg border border-border bg-surface p-4">
          <h2 className="text-[13px] font-semibold text-ink">Добавить Mail.ru</h2>
          <p className="mt-1 text-[12px] text-ink-muted">Нужен отдельный пароль приложения с правом «Полный доступ к Почте».</p>

          <div className="mt-3 space-y-2.5">
            <label className="block">
              <span className="mb-1 block text-[11.5px] font-medium text-ink-soft">Email</span>
              <input
                type="email"
                autoComplete="off"
                value={mailruEmail}
                onChange={(e) => setMailruEmail(e.target.value)}
                placeholder="name@mail.ru"
                className="h-9 w-full rounded-md border border-border-strong bg-canvas px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[11.5px] font-medium text-ink-soft">Пароль приложения</span>
              <input
                type="password"
                autoComplete="new-password"
                value={mailruPassword}
                onChange={(e) => setMailruPassword(e.target.value)}
                placeholder="Не обычный пароль"
                className="h-9 w-full rounded-md border border-border-strong bg-canvas px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
              />
            </label>
          </div>

          {mailruError && <p className="mt-2 text-[12px] text-danger">{mailruError}</p>}
          {mailruMessage && <p className="mt-2 text-[12px] text-success">{mailruMessage}</p>}

          <div className="mt-3 flex items-center gap-3">
            <Button variant="primary" size="sm" icon={mailruConnecting ? <Loader2 size={13} className="animate-spin" /> : <Mail size={13} />} disabled={mailruConnecting} onClick={() => void handleMailruConnect()}>
              Подключить Mail.ru
            </Button>
            <a
              href="https://help.mail.ru/mail/login/mailer/"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-[12px] text-accent hover:underline"
            >
              Открыть официальную инструкцию <ExternalLink size={11} />
            </a>
          </div>

          <details className="mt-3 rounded-md border border-border bg-canvas px-3 py-2 text-[12px] text-ink-soft">
            <summary className="cursor-pointer font-medium text-ink">Как получить пароль приложения?</summary>
            <ol className="mt-2 list-decimal space-y-1 pl-4">
              <li>Откройте Mail.ru и перейдите в настройки.</li>
              <li>Откройте «Все настройки» → «Безопасность».</li>
              <li>Выберите «Пароли для внешних приложений».</li>
              <li>Создайте пароль для SupplyDesk и выберите «Полный доступ к Почте».</li>
              <li>Вставьте созданный пароль в форму выше.</li>
            </ol>
          </details>

          <div className="mt-3 flex items-start gap-2 rounded-md border border-warning-border bg-warning-subtle px-3 py-2 text-[11.5px] text-warning">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            Обычный пароль Mail.ru не подходит. SupplyDesk проверяет SMTP и IMAP по защищённым каналам; письмо не отправляется во время подключения.
          </div>
        </div>
      </div>
    </div>
  );
}
