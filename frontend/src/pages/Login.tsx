import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { KeyRound, Lock, Mail } from 'lucide-react';
import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';

const YANDEX_ERROR_LABELS: Record<string, string> = {
  not_configured: 'Вход через Яндекс сейчас недоступен на сервере.',
  invalid_state: 'Сессия входа устарела, попробуйте ещё раз.',
  access_denied: 'Вы отменили вход через Яндекс.',
  missing_code: 'Яндекс не передал код авторизации, попробуйте ещё раз.',
  connection_failed: 'Не удалось связаться с Яндексом, попробуйте ещё раз.',
};

export function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [searchParams] = useSearchParams();
  const [showLocalLogin, setShowLocalLogin] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const yandexErrorCode = searchParams.get('error');
  const [error, setError] = useState(
    yandexErrorCode ? YANDEX_ERROR_LABELS[yandexErrorCode] ?? 'Не удалось войти через Яндекс.' : '',
  );
  const [submitting, setSubmitting] = useState(false);

  const handleYandexLogin = () => {
    window.location.href = '/api/auth/yandex/start';
  };

  const handleLocalLogin = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50 px-6">
      <div className="w-full max-w-[380px] animate-fade-in">
        <div className="flex flex-col items-center text-center">
          <span className="mb-5 flex h-12 w-12 items-center justify-center rounded-xl bg-accent-600 text-xl font-bold text-white">›</span>
          <h1 className="text-xl font-bold tracking-tight text-ink-900">SupplyDesk</h1>
          <p className="mt-1.5 text-sm text-ink-500">Войдите, чтобы продолжить работу с заявками</p>
        </div>

        <div className="mt-8 rounded-2xl border border-ink-200 bg-white p-6 shadow-soft">
          {error && !showLocalLogin && (
            <p className="mb-4 rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700">{error}</p>
          )}

          <button
            onClick={handleYandexLogin}
            className="flex h-11 w-full items-center justify-center gap-2.5 rounded-xl bg-ink-900 text-sm font-semibold text-white transition hover:bg-ink-800"
          >
            <KeyRound size={16} />Войти с помощью Яндекса
          </button>

          {!showLocalLogin ? (
            <button
              onClick={() => setShowLocalLogin(true)}
              className="mt-4 w-full text-center text-xs font-medium text-ink-400 transition hover:text-ink-700"
            >
              Локальный вход для разработки
            </button>
          ) : (
            <form onSubmit={handleLocalLogin} className="mt-4 space-y-2.5 border-t border-ink-100 pt-4 animate-fade-in">
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                  className="h-10 w-full rounded-lg border border-ink-200 bg-white pl-9 pr-3 text-sm text-ink-800 placeholder:text-ink-400 transition-colors focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-100"
                />
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Пароль"
                  className="h-10 w-full rounded-lg border border-ink-200 bg-white pl-9 pr-3 text-sm text-ink-800 placeholder:text-ink-400 transition-colors focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-100"
                />
              </div>
              {error && <p className="text-left text-xs font-medium text-rose-600">{error}</p>}
              <button
                type="submit"
                disabled={submitting}
                className="h-10 w-full rounded-lg bg-accent-600 text-sm font-semibold text-white transition hover:bg-accent-700 disabled:opacity-50"
              >
                {submitting ? 'Входим…' : 'Войти'}
              </button>
            </form>
          )}
        </div>

        <p className="mt-6 text-center text-[11px] text-ink-400">Procurement OS · внутренний инструмент отдела снабжения</p>
      </div>
    </div>
  );
}
