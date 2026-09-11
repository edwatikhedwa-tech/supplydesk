import { useEffect, useState } from 'react';

/** Below this width a desktop multi-column layout (sidebar rail, 3-pane
 * Messages view, side-docked panels) stops being usable -- columns compress
 * until labels wrap one word per line. Shared by every screen that switches
 * to a single-pane mobile layout below this breakpoint. */
export const MOBILE_BREAKPOINT_PX = 768;

export function useIsNarrowViewport(breakpoint = MOBILE_BREAKPOINT_PX): boolean {
  const [narrow, setNarrow] = useState(() => typeof window !== 'undefined' && window.innerWidth < breakpoint);
  useEffect(() => {
    const query = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const onChange = () => setNarrow(query.matches);
    onChange();
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, [breakpoint]);
  return narrow;
}
