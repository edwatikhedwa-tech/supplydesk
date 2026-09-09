import { lazy, Suspense, useState, type FormEvent } from 'react';
import { useAuth } from '../lib/AuthContext';
import { Button } from '../components/ui/Button';

const MagicRings = lazy(() => import('../components/MagicRings'));

const YANDEX_ERROR_LABELS: Record<string, string> = {
  access_denied: 'Вход через Яндекс отменён.',
  missing_code: 'Яндекс не вернул код авторизации. Попробуйте ещё раз.',
  connection_failed: 'Не удалось завершить вход через Яндекс.',
  invalid_state: 'Сессия входа истекла. Попробуйте ещё раз.',
};

function YandexIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-4 w-4 shrink-0" aria-hidden="true">
      <rect width="32" height="32" rx="16" fill="#fc3f1d" />
      <path
        fill="#fff"
        d="M20.96 24h-3.1V8.63h-1.38c-2.54 0-3.87 1.27-3.87 3.16 0 2.15.92 3.15 2.81 4.42l1.56 1.05-4.49 6.74H9.15l4.04-6.02c-2.1-1.6-3.37-3.22-3.37-5.96 0-3.42 2.38-5.74 6.89-5.74h4.25V24Z"
      />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-4 w-4 shrink-0" aria-hidden="true">
      <rect width="32" height="32" rx="16" fill="#fff" />
      <path fill="#4285f4" d="M26.2 16.34c0-.73-.07-1.44-.2-2.12H16v4.01h5.71a4.88 4.88 0 0 1-2.12 3.2v2.66h3.43c2.01-1.85 3.18-4.57 3.18-7.75Z" />
      <path fill="#34a853" d="M16 26.7c2.88 0 5.3-.95 7.07-2.61l-3.43-2.66c-.95.64-2.17 1.02-3.64 1.02-2.8 0-5.17-1.9-6.02-4.45H6.43v2.74A10.68 10.68 0 0 0 16 26.7Z" />
      <path fill="#fbbc05" d="M9.98 18a6.42 6.42 0 0 1 0-4.01v-2.74H6.43a10.7 10.7 0 0 0 0 9.49L9.98 18Z" />
      <path fill="#ea4335" d="M16 9.54c1.57 0 2.98.54 4.09 1.6l3.07-3.07C21.3 6.31 18.88 5.3 16 5.3a10.68 10.68 0 0 0-9.57 5.95l3.55 2.74c.85-2.55 3.22-4.45 6.02-4.45Z" />
    </svg>
  );
}

function MailRuIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-4 w-4 shrink-0" aria-hidden="true">
      <rect width="32" height="32" rx="16" fill="#087cff" />
      <path
        fill="#fff"
        d="M16 6C10.49 6 6 10.49 6 16s4.49 10 10 10c2.02 0 3.97-.6 5.63-1.74l.03-.02-1.35-1.57-.02.02A7.9 7.9 0 0 1 16 23.95 7.95 7.95 0 1 1 23.95 16c0 2.2-.87 3.16-1.7 3.08-.55-.05-1.18-.43-1.19-1.38V16A5.06 5.06 0 1 0 16 21.06c1.36 0 2.63-.53 3.58-1.5a3.25 3.25 0 0 0 2.77 1.51c.73 0 1.45-.24 2.03-.69.6-.45 1.05-1.11 1.29-1.9.04-.13.11-.42.11-.42l.01-.01c.15-.65.21-1.28.21-2.06C26 10.49 21.51 6 16 6Zm3.01 10A3.01 3.01 0 1 1 13 16a3.01 3.01 0 0 1 6.01 0Z"
      />
    </svg>
  );
}

export function Login() {
  const { login, error, sessionExpired } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);
  const [ringsSupported, setRingsSupported] = useState(true);

  const yandexErrorCode = new URLSearchParams(window.location.search).get('error');
  const yandexError = yandexErrorCode ? YANDEX_ERROR_LABELS[yandexErrorCode] ?? 'Не удалось войти через Яндекс.' : '';

  function handleYandexLogin() {
    window.location.href = '/api/auth/yandex/start';
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    try {
      await login(email, password);
    } catch {
      // error is surfaced via useAuth().error
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="relative isolate flex h-screen w-screen items-center justify-center overflow-hidden bg-[#070b17]">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-0">
        {ringsSupported ? (
          <Suspense fallback={null}>
            <MagicRings
              color="#2f8cff"
              colorTwo="#163c90"
              ringCount={7}
              speed={0.6}
              attenuation={12}
              lineThickness={1.5}
              baseRadius={0.2}
              radiusStep={0.12}
              scaleRate={0.08}
              opacity={0.45}
              blur={1}
              noiseAmount={0.035}
              fadeIn={0.8}
              fadeOut={0.4}
              followMouse
              mouseInfluence={0.15}
              hoverScale={1.1}
              parallax={0.04}
              clickBurst
              onUnsupported={() => setRingsSupported(false)}
            />
          </Suspense>
        ) : (
          <div className="absolute left-1/2 top-1/2 h-[min(94vw,720px)] w-[min(94vw,720px)] -translate-x-1/2 -translate-y-1/2 rounded-full border border-blue-400/20 shadow-[0_0_90px_rgba(45,145,255,0.18),inset_0_0_80px_rgba(45,145,255,0.08)]" />
        )}
      </div>
      <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_50%_42%,rgba(21,91,190,0.17),transparent_34%),linear-gradient(180deg,rgba(7,11,23,0.18),rgba(7,11,23,0.76))]" />

      <div className="relative z-10 w-full max-w-[340px] rounded-lg border border-border bg-surface p-6 shadow-[0_20px_60px_rgba(0,0,0,0.45)]">
        <p className="font-display text-[18px] font-semibold text-ink">SupplyDesk</p>
        <p className="mt-1 text-[12.5px] text-ink-muted">Вход в рабочее пространство снабжения</p>

        {sessionExpired && !yandexError && (
          <p className="mt-3 text-[12px] text-warning">Сессия истекла — войдите ещё раз.</p>
        )}
        {yandexError && <p className="mt-3 text-[12px] text-danger">{yandexError}</p>}

        <Button
          type="button"
          variant="secondary"
          className="mt-5 w-full"
          icon={<YandexIcon />}
          onClick={handleYandexLogin}
        >
          Войти через Яндекс
        </Button>

        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            disabled
            title="Пока не подключено"
            className="flex h-9 flex-1 items-center justify-center gap-2 rounded-md border border-border bg-surface text-[13px] font-medium text-ink-faint opacity-60"
          >
            <GoogleIcon />
            Google
          </button>
          <button
            type="button"
            disabled
            title="Пока не подключено"
            className="flex h-9 flex-1 items-center justify-center gap-2 rounded-md border border-border bg-surface text-[13px] font-medium text-ink-faint opacity-60"
          >
            <MailRuIcon />
            Mail.ru
          </button>
        </div>
        <p className="mt-1.5 text-center text-[10.5px] text-ink-faint">Google и Mail.ru — скоро</p>

        <div className="mt-4 flex items-center gap-2">
          <div className="h-px flex-1 bg-border" />
          <span className="text-[11px] text-ink-muted">или по паролю</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <form onSubmit={handleSubmit}>
        <label className="mt-3 block text-[12px] font-medium text-ink-soft">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="mt-1 h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
        />

        <label className="mt-3 block text-[12px] font-medium text-ink-soft">Пароль</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="mt-1 h-9 w-full rounded-md border border-border-strong bg-surface px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
        />

        {error && <p className="mt-3 text-[12px] text-danger">{error}</p>}

        <Button type="submit" variant="primary" className="mt-5 w-full" disabled={pending}>
          {pending ? 'Входим…' : 'Войти'}
        </Button>
        </form>
      </div>
    </div>
  );
}
