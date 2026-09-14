import { lazy, Suspense, useState, type CSSProperties, type FormEvent, type ReactElement } from 'react';
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
    <svg viewBox="0 0 32 32" className="h-full w-full" aria-hidden="true">
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
    <svg viewBox="0 0 32 32" className="h-full w-full" aria-hidden="true">
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
    <svg viewBox="0 0 32 32" className="h-full w-full" aria-hidden="true">
      <rect width="32" height="32" rx="16" fill="#087cff" />
      <path fill="#fff" d="M16 6C10.49 6 6 10.49 6 16s4.49 10 10 10c2.02 0 3.97-.6 5.63-1.74l.03-.02-1.35-1.57-.02.02A7.9 7.9 0 0 1 16 23.95 7.95 7.95 0 1 1 23.95 16c0 2.2-.87 3.16-1.7 3.08-.55-.05-1.18-.43-1.19-1.38V16A5.06 5.06 0 1 0 16 21.06c1.36 0 2.63-.53 3.58-1.5a3.25 3.25 0 0 0 2.77 1.51c.73 0 1.45-.24 2.03-.69.6-.45 1.05-1.11 1.29-1.9.04-.13.11-.42.11-.42l.01-.01c.15-.65.21-1.28.21-2.06C26 10.49 21.51 6 16 6Zm3.01 10A3.01 3.01 0 1 1 13 16a3.01 3.01 0 0 1 6.01 0Z" />
    </svg>
  );
}

type LoginProvider = 'yandex' | 'google' | 'mailru';

const PROVIDERS: Array<{ id: LoginProvider; label: string; color: string; enabled: boolean; Icon: () => ReactElement }> = [
  { id: 'yandex', label: 'Яндекс', color: '#fc3f1d', enabled: true, Icon: YandexIcon },
  { id: 'google', label: 'Google', color: '#4285f4', enabled: false, Icon: GoogleIcon },
  { id: 'mailru', label: 'Mail.ru', color: '#087cff', enabled: false, Icon: MailRuIcon },
];

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

      <div className="relative z-10 w-full max-w-[356px] p-6 sm:p-7">
        <p className="font-display text-[20px] font-semibold tracking-[-0.02em] text-white">SupplyDesk</p>
        <p className="mt-1 text-[12.5px] text-slate-300">Вход в рабочее пространство снабжения</p>

        {sessionExpired && !yandexError && (
          <p className="mt-3 text-[12px] text-amber-300">Сессия истекла — войдите ещё раз.</p>
        )}
        {yandexError && <p className="mt-3 text-[12px] text-danger">{yandexError}</p>}

        <section aria-label="Выбор почтового входа" className="mt-5">
          <p className="text-center text-[12px] font-medium text-slate-200">Войти через почту</p>
          <div className="mt-3 flex items-start justify-center gap-4">
            {PROVIDERS.map((provider) => {
              const Icon = provider.Icon;
              return (
                <div key={provider.id} className="flex w-[72px] flex-col items-center gap-1.5">
                  <button
                    type="button"
                    disabled={!provider.enabled}
                    onClick={provider.enabled ? handleYandexLogin : undefined}
                    aria-label={provider.enabled ? `Войти через ${provider.label}` : `${provider.label}: скоро`}
                    title={provider.enabled ? `Войти через ${provider.label}` : `${provider.label} — скоро`}
                    className="group relative h-12 w-12 rounded-full outline-none transition duration-200 hover:scale-105 focus-visible:ring-2 focus-visible:ring-blue-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#070b17] disabled:cursor-not-allowed disabled:opacity-50"
                    style={{ '--provider-color': provider.color } as CSSProperties}
                  >
                    <span aria-hidden="true" className="absolute inset-[-4px] rounded-full bg-[var(--provider-color)] opacity-20 blur-md transition group-hover:opacity-45" />
                    <span aria-hidden="true" className="absolute inset-0 rounded-full border-2 border-[var(--provider-color)] opacity-70 transition group-hover:opacity-100" />
                    <span className="relative block h-full w-full overflow-hidden rounded-full bg-slate-950/80 shadow-[0_7px_20px_rgba(0,0,0,0.36)]">
                      <Icon />
                    </span>
                  </button>
                  <span className="text-[10.5px] font-medium text-slate-300">{provider.label}</span>
                  {!provider.enabled && <span className="-mt-1 text-[9px] text-slate-500">Скоро</span>}
                </div>
              );
            })}
          </div>
        </section>

        <div className="mt-4 flex items-center gap-2">
          <div className="h-px flex-1 bg-white/15" />
          <span className="text-[11px] text-slate-400">или по email и паролю</span>
          <div className="h-px flex-1 bg-white/15" />
        </div>

        <form onSubmit={handleSubmit}>
        <label className="mt-3 block text-[12px] font-medium text-slate-200">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="mt-1 h-10 w-full rounded-lg border border-white/20 bg-slate-950/55 px-3 text-[13px] text-white outline-none placeholder:text-slate-600 focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
        />

        <label className="mt-3 block text-[12px] font-medium text-slate-200">Пароль</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="mt-1 h-10 w-full rounded-lg border border-white/20 bg-slate-950/55 px-3 text-[13px] text-white outline-none placeholder:text-slate-600 focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
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
