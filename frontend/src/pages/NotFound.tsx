import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';

export function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-100 text-ink-400">
        <Compass size={24} />
      </div>
      <div>
        <h1 className="text-xl font-bold text-ink-900">Страница не найдена</h1>
        <p className="mt-1.5 max-w-sm text-sm text-ink-500">Такого адреса нет в приложении — возможно, ссылка устарела или в ней опечатка.</p>
      </div>
      <Link to="/" className="mt-2 inline-flex items-center gap-2 rounded-xl bg-accent-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-700">
        На дашборд
      </Link>
    </div>
  );
}
