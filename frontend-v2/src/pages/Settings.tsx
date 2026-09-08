import { AlertTriangle, Check, ExternalLink, Loader2, Mail, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PageHeader } from '../components/shell/PageHeader';
import { Button } from '../components/ui/Button';
import { ErrorState, LoadingState } from '../components/ui/ErrorState';
import { ApiError, api } from '../lib/api';
import { formatDateTime } from '../lib/format';
import type { MailAccount } from '../lib/types';
import { useApiData } from '../lib/useApiData';

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
  const [disconnecting, setDisconnecting] = useState(false);
  const [message, setMessage] = useState('');

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

      <div className="mt-3 grid grid-cols-3 gap-2.5">
        <MiniStat label="Аккаунт" value={account.connected ? 'Подключён' : 'Нужна проверка'} tone={account.connected ? 'success' : 'warning'} />
        <MiniStat label="Исходящие" value={outgoingLabel} tone={outgoingTone} />
        <MiniStat label="Входящие ответы" value={incoming.label} tone={incoming.tone} />
      </div>

      <p className="mt-2.5 text-[11px] text-ink-faint">
        Последняя проверка: {account.incoming_last_success_at ? formatDateTime(account.incoming_last_success_at) : 'не проверялась'}
      </p>
      {incomingError && <p className="mt-1 text-[11px] font-medium text-danger">Ошибка входящих: {incomingError}</p>}
      {message && <p className="mt-1.5 text-[11.5px] text-ink-soft">{message}</p>}

      <div className="mt-3 flex items-center gap-2">
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
          variant="ghost"
          size="sm"
          className="ml-auto text-danger hover:bg-danger-subtle"
          icon={<Trash2 size={13} />}
          disabled={disconnecting}
          onClick={() => void handleDisconnect()}
        >
          Отключить
        </Button>
      </div>
    </div>
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
        <PageHeader title="Настройки" />
        <LoadingState label="Загружаем настройки почты…" />
      </div>
    );
  }
  if (state.status === 'error') {
    return (
      <div className="flex h-full flex-col overflow-auto">
        <PageHeader title="Настройки" />
        <ErrorState message={state.message} onRetry={state.reload} />
      </div>
    );
  }

  const accounts = state.data.accounts;
  const hasConnectedYandex = accounts.some((a) => a.provider === 'yandex' && a.connected);

  return (
    <div className="flex h-full flex-col overflow-auto">
      <PageHeader title="Настройки" description="Почтовые аккаунты для отправки и приёма писем поставщиков" />

      <div className="max-w-2xl space-y-4 px-6 pb-6">
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
