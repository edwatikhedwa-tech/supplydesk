import { useEffect, useState } from 'react';
import { ApiError } from './api';

type AsyncState<T> = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: T };

/** Fetches once on mount. `deps` controls re-fetching, same as useEffect. */
export function useApiData<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> & { reload: () => void; mutate: (updater: (data: T) => T) => void } {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    // Only show the loading state for the first fetch. A `reload()` while data is
    // already on screen keeps showing that stale data instead of unmounting the
    // whole subtree (which would wipe any local state, e.g. an action's result message).
    setState((prev) => (prev.status === 'ready' ? prev : { status: 'loading' }));
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

  return {
    ...state,
    reload: () => setTick((t) => t + 1),
    // Applies a known-good result locally (e.g. after a write the server
    // already confirmed) instead of refetching -- a full reload() replaces
    // every item's object identity and re-sorts/re-filters the whole list,
    // which visibly jumps a scrolled list back toward the top. No-ops if
    // data hasn't loaded yet (nothing to patch).
    mutate: (updater: (data: T) => T) => setState((prev) => (prev.status === 'ready' ? { status: 'ready', data: updater(prev.data) } : prev)),
  } as AsyncState<T> & { reload: () => void; mutate: (updater: (data: T) => T) => void };
}
