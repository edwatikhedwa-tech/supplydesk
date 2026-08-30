import { lazy, Suspense, useState, type CSSProperties } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
/** Фон входа тянет three.js (~600 КБ). Экран входа открывают один раз за
 *  сессию, а бандл до этой правки грузился на каждой странице приложения.
 *  Ленивая загрузка: сам экран рисуется сразу, кольца доезжают следом. */
const MagicRings = lazy(() => import('@/components/MagicRings'));

const YANDEX_ERROR_LABELS: Record<string, string> = {
  not_configured: 'Вход через Яндекс сейчас недоступен на сервере.',
  invalid_state: 'Сессия входа устарела, попробуйте ещё раз.',
  access_denied: 'Вы отменили вход через Яндекс.',
  missing_code: 'Яндекс не передал код авторизации, попробуйте ещё раз.',
  connection_failed: 'Не удалось связаться с Яндексом, попробуйте ещё раз.',
};

type Provider = 'yandex' | 'google' | 'mailru';

function SupplyDeskMark() {
  return (
    <svg viewBox="0 0 80 80" className="h-full w-full" role="img" aria-label="SupplyDesk">
      <defs>
        <linearGradient id="login-mark-blue" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#66efff" />
          <stop offset="42%" stopColor="#1999ff" />
          <stop offset="100%" stopColor="#1555ff" />
        </linearGradient>
        <linearGradient id="login-mark-violet" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#b8a5ff" />
          <stop offset="42%" stopColor="#5c77ff" />
          <stop offset="100%" stopColor="#273b9e" />
        </linearGradient>
        <linearGradient id="login-mark-cyan" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#4be7ff" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
        <filter id="login-mark-shadow" x="-15%" y="-15%" width="130%" height="140%">
          <feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#071026" floodOpacity="0.32" />
        </filter>
      </defs>

      <circle cx="40" cy="40" r="28" fill="#0b82ff" opacity="0.13" />
      <circle cx="40" cy="40" r="25" fill="none" stroke="#65e9ff" strokeWidth="0.7" opacity="0.2" />

      <g filter="url(#login-mark-shadow)">
        <path d="M24 28c0-4 4-6 9-6 5 0 8 2 8 6 0 3-3 5-8 6-5 1-8 2-8 5 0 4 3 6 8 6s8-2 8-6" fill="none" stroke="url(#login-mark-blue)" strokeWidth="6" strokeLinecap="round" />
        <path d="M56 52c0 4-4 6-9 6-5 0-8-2-8-6 0-3 3-5 8-6 5-1 8-2 8-5 0-4-3-6-8-6s-8 2-8 6" fill="none" stroke="url(#login-mark-violet)" strokeWidth="6" strokeLinecap="round" />
        <g transform="translate(40 40)">
          <path d="M-6-2 0-5l6 3v6l-6 3-6-3Z" fill="url(#login-mark-cyan)" />
          <path d="M-6-2 0 1v6l-6-3Z" fill="#0891b2" opacity="0.58" />
          <path d="M6-2 0 1v6l6-3Z" fill="#22d3ee" opacity="0.32" />
          <path d="M-6-2 0 1l6-3" fill="none" stroke="#fff" strokeWidth="0.8" opacity="0.72" />
        </g>
      </g>
    </svg>
  );
}

function YandexIcon() {
  return (
    <svg viewBox="0 0 32 32" className="h-full w-full" aria-hidden="true">
      <rect width="32" height="32" rx="16" fill="#fc3f1d" />
      <path fill="#fff" d="M20.96 24h-3.1V8.63h-1.38c-2.54 0-3.87 1.27-3.87 3.16 0 2.15.92 3.15 2.81 4.42l1.56 1.05-4.49 6.74H9.15l4.04-6.02c-2.1-1.6-3.37-3.22-3.37-5.96 0-3.42 2.38-5.74 6.89-5.74h4.25V24Z" />
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

const PROVIDERS: Array<{ id: Provider; name: string; color: string; icon: () => JSX.Element }> = [
  { id: 'yandex', name: 'Яндекс', color: '#fc3f1d', icon: YandexIcon },
  { id: 'google', name: 'Google', color: '#4285f4', icon: GoogleIcon },
  { id: 'mailru', name: 'Mail.ru', color: '#087cff', icon: MailRuIcon },
];

export function Login() {
  const [searchParams] = useSearchParams();
  const [ringsSupported, setRingsSupported] = useState(true);
  const yandexErrorCode = searchParams.get('error');
  const [error, setError] = useState(
    yandexErrorCode ? YANDEX_ERROR_LABELS[yandexErrorCode] ?? 'Не удалось войти через Яндекс.' : '',
  );

  const handleSocialLogin = (provider: Provider) => {
    if (provider === 'yandex') {
      window.location.href = '/api/auth/yandex/start';
      return;
    }

    const providerName = PROVIDERS.find((item) => item.id === provider)?.name ?? 'Этот способ';
    setError(`Вход через ${providerName} пока не подключён.`);
  };

  return (
    <div className="relative isolate flex min-h-screen w-full items-center justify-center overflow-hidden bg-[#070b17] px-5 py-0 text-white sm:px-8">
      <style>{`
        @keyframes login-spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes login-logo-drop {
          0% { transform: translateY(-170px) rotate(-14deg); opacity: 0; filter: blur(6px); }
          58% { transform: translateY(10px) rotate(3deg); opacity: 1; filter: blur(0); }
          76% { transform: translateY(-5px) rotate(-1deg); }
          100% { transform: translateY(0) rotate(0); opacity: 1; filter: blur(0); }
        }
        @keyframes login-logo-glint {
          0%, 88% { transform: translateX(-190%) rotate(24deg); opacity: 0; }
          90% { opacity: 0.1; }
          94% { opacity: 0.95; }
          98%, 100% { transform: translateX(240%) rotate(24deg); opacity: 0; }
        }
        .login-spin { animation: login-spin 2.4s linear infinite; }
        .login-logo-drop { animation: login-logo-drop 980ms cubic-bezier(.18,.89,.32,1.18) both; }
        .login-logo-glint { animation: login-logo-glint 15s ease-in-out 2s infinite; }
        @media (prefers-reduced-motion: reduce) {
          .login-spin, .login-logo-drop, .login-logo-glint { animation: none; }
        }
      `}</style>

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
      <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_50%_50%,transparent_12%,rgba(2,5,14,0.3)_74%,rgba(2,5,14,0.7))]" />

      <main className="relative z-10 flex w-full max-w-[440px] flex-col items-center">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="relative mb-5 h-[88px] w-[88px]">
            <div className="login-spin absolute inset-[-5px] rounded-[28px] border border-blue-300/55 border-t-cyan-200/90 border-r-transparent" />
            <div className="login-logo-drop relative h-full w-full overflow-hidden">
              <SupplyDeskMark />
              <span className="login-logo-glint pointer-events-none absolute left-[-42%] top-[-45%] h-[190%] w-[20%] rotate-[24deg] bg-gradient-to-r from-transparent via-white/90 to-transparent blur-[3px]" />
            </div>
          </div>
          <div className="mb-2 flex items-center gap-3 text-2xs font-semibold uppercase tracking-[0.38em] text-blue-200/80">
            <span className="h-px w-8 bg-blue-300/40" />
            SupplyDesk
            <span className="h-px w-8 bg-blue-300/40" />
          </div>
          <h1 className="text-display-title font-semibold text-white">Вход в рабочее пространство</h1>
        </div>

        <section className="w-full px-0 py-5 sm:py-6">
          <div className="mb-5 text-center">
            <p className="text-sm font-semibold text-white">Выберите способ входа</p>
            <p className="mt-1 text-xs text-slate-400">Безопасный доступ к внутренним инструментам</p>
          </div>

          {error && (
            <p role="alert" className="mb-5 rounded-xl border border-rose-300/15 bg-rose-400/10 px-3.5 py-3 text-center text-xs font-medium leading-5 text-rose-200">
              {error}
            </p>
          )}

          <div className="flex items-center justify-center gap-4 sm:gap-5">
            {PROVIDERS.map((provider) => {
              const Icon = provider.icon;
              return (
                <button
                  key={provider.id}
                  type="button"
                  onClick={() => handleSocialLogin(provider.id)}
                  aria-label={`Войти через ${provider.name}`}
                  title={provider.id === 'yandex' ? 'Войти через Яндекс' : `${provider.name} пока не подключён`}
                  className="group relative h-[68px] w-[68px] rounded-full transition duration-300 hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300/80 focus-visible:ring-offset-4 focus-visible:ring-offset-[#0b1222]"
                  style={{ '--provider-color': provider.color } as CSSProperties}
                >
                  <span className="absolute inset-0 rounded-full bg-[var(--provider-color)] opacity-25 blur-md transition duration-300 group-hover:opacity-60" />
                  <span className="absolute inset-[-4px] rounded-full bg-[var(--provider-color)] opacity-25 blur-lg transition duration-300 group-hover:opacity-65" />
                  <span className="absolute inset-0 rounded-full border-2 border-[var(--provider-color)] opacity-60 transition duration-300 group-hover:opacity-100" />
                  <span className="absolute inset-[-1px] rounded-full border border-white/10" />
                  <span className="relative block h-full w-full overflow-hidden rounded-full shadow-[0_8px_24px_rgba(0,0,0,0.3)] transition duration-300 group-hover:scale-105">
                    <Icon />
                  </span>
                  <span className="absolute inset-0 rounded-full border-2 border-[var(--provider-color)] opacity-0 transition duration-300 group-hover:animate-ping group-hover:opacity-60" />
                </button>
              );
            })}
          </div>

        </section>

        <div className="mt-6 flex items-center gap-2 text-xs text-slate-400/75">
          <ShieldCheck size={14} className="text-cyan-300/80" />
          Доступ только для команды снабжения
        </div>
        <p className="mt-3 max-w-[340px] text-center text-2xs leading-5 text-slate-500">
          Продолжая, вы соглашаетесь с <span className="text-blue-300/80">условиями использования</span> и <span className="text-blue-300/80">политикой конфиденциальности</span>.
        </p>
        <p className="mt-1 text-2xs tracking-wide text-slate-600">Procurement OS · внутренний инструмент отдела снабжения</p>
      </main>
    </div>
  );
}
