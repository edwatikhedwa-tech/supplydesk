import { useEffect, useState } from 'react';
import { ApiError } from './api';

type AsyncState<T> = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: T };

/** Fetches once on mount. `deps` controls re-fetching, same as useEffect. */
export function useApiData<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncState<T> & { reload: () => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading' });
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data });
      })
      .catch((e) => {
        if (cancelled) return;
        const message = e instanceof ApiError ? e.message : 'Не удалось получить данные с сервера.';
        setState({ status: 'error', message });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) } as AsyncState<T> & { reload: () => void };
}
