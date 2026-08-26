import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Loader2, Mail, RefreshCw, Unplug } from 'lucide-react';
import { api } from '@/lib/api';

const MAIL_ERROR_LABELS: Record<string, string> = {
  not_configured: 'Подключение к Яндекс.Почте сейчас недоступно на сервере.',
  access_denied: 'Вы отменили подключение почты в Яндексе.',
  missing_code: 'Яндекс не передал код авторизации, попробуйте ещё раз.',
  connection_failed: 'Не удалось подключить почту, попробуйте ещё раз.',
};

interface MailStatus {
  connected: boolean;
  provider?: string;
  email?: string;
  status?: string;
  last_error?: string | null;
  updated_at?: string | null;
}

export function Settings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<MailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');

  const mailErrorCode = searchParams.get('mail_error');
  const justConnected = searchParams.get('connected') === 'true';

  const load = () => {
    setLoading(true);
    return api.mailStatus().then(setStatus).finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    if (mailErrorCode || justConnected) {
      // Query params are one-shot feedback from the OAuth redirect — clear them
      // so a page refresh doesn't keep re-showing the same banner.
      searchParams.delete('mail_error');
      searchParams.delete('connected');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTest = async () => {
    setTesting(true);
    setActionMessage('');
    setActionError('');
    try {
      const res = await api.mailTest();
      setActionMessage(res.message);
      await load();
    } catch {
      setActionError('Не удалось проверить соединение.');
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    setActionMessage('');
    setActionError('');
    try {
      const res = await api.mailSync();
      setActionMessage(`Синхронизация выполнена: получено ${res.imported ?? 0}.`);
    } catch {
      setActionError('Не удалось синхронизировать почту.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    setActionMessage('');
    setActionError('');
    try {
      await api.mailDisconnect();
      await load();
    } catch {
      setActionError('Не удалось отключить почту.');
    } finally {
      setDisconnecting(false);
    }
  };

  const handleConnect = () => {
    window.location.href = '/api/mail/yandex/start';
  };

  return (
    <div className="min-h-screen px-6 py-7 lg:px-10 lg:py-10 animate-fade-in">
      <div className="mx-auto max-w-[760px] space-y-6">
        <div>
          <h1 className="text-[28px] font-bold tracking-tight">Настройки</h1>
          <p className="mt-1 text-sm text-ink-500">Подключение почты и параметры рабочего пространства.</p>
        </div>

        {justConnected && (
          <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4 shrink-0" />Почта успешно подключена.
          </div>
        )}
        {mailErrorCode && (
          <div className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <AlertCircle className="h-4 w-4 shrink-0" />{MAIL_ERROR_LABELS[mailErrorCode] ?? 'Не удалось подключить почту.'}
          </div>
        )}

        <section className="space-y-4 rounded-2xl border border-ink-200/80 bg-white p-6 shadow-soft">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-ink-400" />
            <h2 className="text-base font-bold text-ink-900">Почта</h2>
          </div>

          {loading ? (
            <div className="py-6 text-center text-sm text-ink-400">Загрузка…</div>
          ) : status?.connected ? (
            <>
              <div className="flex items-center justify-between rounded-xl bg-ink-50/60 px-4 py-3">
                <div>
                  <div className="text-sm font-semibold text-ink-800">{status.email}</div>
                  <div className="mt-0.5 text-xs text-ink-500">Яндекс.Почта · подключена</div>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                  <CheckCircle2 className="h-3.5 w-3.5" />Подключена
                </span>
              </div>

              {status.last_error && (
                <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">Последняя ошибка: {status.last_error}</p>
              )}

              {actionMessage && <p className="text-xs font-medium text-emerald-700">{actionMessage}</p>}
              {actionError && <p className="text-xs font-medium text-rose-600">{actionError}</p>}

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleTest}
                  disabled={testing}
                  className="inline-flex items-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-700 transition hover:border-ink-300 disabled:opacity-50"
                >
                  {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}Проверить соединение
                </button>
                <button
                  onClick={handleSync}
                  disabled={syncing}
                  className="inline-flex items-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-700 transition hover:border-ink-300 disabled:opacity-50"
                >
                  {syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}Синхронизировать входящие
                </button>
                <button
                  onClick={handleDisconnect}
                  disabled={disconnecting}
                  className="inline-flex items-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-rose-600 transition hover:border-rose-200 hover:bg-rose-50 disabled:opacity-50"
                >
                  {disconnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unplug className="h-3.5 w-3.5" />}Отключить
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-ink-500">Почта не подключена — отправка запросов поставщикам и приём ответов недоступны.</p>
              <button
                onClick={handleConnect}
                className="inline-flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-700"
              >
                <Mail className="h-4 w-4" />Подключить Яндекс.Почту
              </button>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
