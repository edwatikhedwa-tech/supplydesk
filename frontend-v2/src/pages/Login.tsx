import { useState, type FormEvent } from 'react';
import { useAuth } from '../lib/AuthContext';
import { Button } from '../components/ui/Button';

export function Login() {
  const { login, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pending, setPending] = useState(false);

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
    <div className="flex h-screen w-screen items-center justify-center bg-canvas">
      <form onSubmit={handleSubmit} className="w-full max-w-[340px] rounded-lg border border-border bg-surface p-6">
        <p className="font-display text-[18px] font-semibold text-ink">SupplyDesk</p>
        <p className="mt-1 text-[12.5px] text-ink-muted">Вход в рабочее пространство снабжения (реальные данные, LOCAL_CANONICAL)</p>

        <label className="mt-5 block text-[12px] font-medium text-ink-soft">Email</label>
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
  );
}
