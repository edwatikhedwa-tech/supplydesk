import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, setCsrfToken } from '@/lib/api';
import type { AuthUser } from '@/lib/types';
import { isUiPreviewMode, previewUser } from '@/lib/previewFixtures';

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
    if (isUiPreviewMode) {
      setUser(previewUser);
      setStatus('authenticated');
      return undefined;
    }
    let cancelled = false;
    const keepSession = () => {
      refresh().catch(() => {
        if (!cancelled) setStatus('anonymous');
      });
    };

    keepSession();
    // The server renews the persistent session when this heartbeat arrives.
    // It also keeps an open monitoring page authenticated during long campaigns.
    const timer = window.setInterval(keepSession, 15 * 60 * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
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
