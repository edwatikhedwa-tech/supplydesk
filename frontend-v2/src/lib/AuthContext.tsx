import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { ApiError, api, setCsrfToken } from './api';
import type { AuthUser } from './types';

type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

interface AuthState {
  status: AuthStatus;
  user: AuthUser | null;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .me()
      .then((res) => {
        if (res.authenticated && res.user) {
          setCsrfToken(res.csrf_token ?? '');
          setUser(res.user);
          setStatus('authenticated');
        } else {
          setStatus('anonymous');
        }
      })
      .catch(() => setStatus('anonymous'));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const res = await api.login(email, password);
      setCsrfToken(res.csrf_token);
      setUser(res.user);
      setStatus('authenticated');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Не удалось подключиться к бэкенду.');
      throw e;
    }
  }, []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => {});
    setUser(null);
    setCsrfToken('');
    setStatus('anonymous');
  }, []);

  return <AuthContext.Provider value={{ status, user, error, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
