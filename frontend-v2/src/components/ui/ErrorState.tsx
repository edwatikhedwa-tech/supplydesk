import { AlertTriangle } from 'lucide-react';
import { Button } from './Button';

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
      <AlertTriangle size={22} strokeWidth={1.5} className="text-danger" />
      <p className="text-[13px] font-medium text-ink-soft">Не удалось загрузить данные</p>
      <p className="max-w-[40ch] text-[12.5px] text-ink-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} className="mt-1">
          Повторить
        </Button>
      )}
    </div>
  );
}

export function LoadingState({ label = 'Загрузка…' }: { label?: string }) {
  return <div className="flex items-center justify-center py-16 text-[12.5px] text-ink-muted">{label}</div>;
}
