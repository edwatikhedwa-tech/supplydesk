import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, setCsrfToken } from '@/lib/api';
import type { AuthUser } from '@/lib/types';

interface AuthState {
  status: 'loading' | 'authenticated' | 'anonymous';
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState['status']>('loading');
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    const me = await api.me();
    if (me.authenticated && me.user) {
      setCsrfToken(me.csrf_token || '');
      setUser(me.user);
      setStatus('authenticated');
    } else {
      setCsrfToken('');
      setUser(null);
      setStatus('anonymous');
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => setStatus('anonymous'));
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    setCsrfToken(result.csrf_token);
    setUser(result.user);
    setStatus('authenticated');
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setCsrfToken('');
    setUser(null);
    setStatus('anonymous');
  }, []);

  return <AuthContext.Provider value={{ status, user, login, logout, refresh }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
