import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface EmailWorkspaceProps {
  /** The navigator/read-pane composition stays owned by the page for now. */
  children: ReactNode;
  /** Reserved slot for a future request, supplier or notes context panel. */
  contextPanel?: ReactNode;
  contextOpen?: boolean;
  className?: string;
}

/**
 * Stable shell for email-oriented workspaces.
 *
 * This is deliberately a layout contract, not a data or API abstraction:
 * existing mail flows keep ownership of fetching, selection and actions while
 * future context panels can be added without introducing a second page shell.
 */
export function EmailWorkspace({ children, contextPanel, contextOpen = false, className }: EmailWorkspaceProps) {
  return (
    <div className={cn('sd-email-workspace flex min-h-0 flex-1 overflow-hidden', className)}>
      {children}
      {contextOpen && contextPanel ? (
        <aside className="hidden w-80 shrink-0 border-l border-ink-200 bg-white xl:block" aria-label="Контекст переписки">
          {contextPanel}
        </aside>
      ) : null}
    </div>
  );
}
