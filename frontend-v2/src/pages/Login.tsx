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
