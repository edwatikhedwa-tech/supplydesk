import { RotateCcw, TriangleAlert } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Button } from './ui/Button';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('Необработанная ошибка в интерфейсе:', error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex h-screen w-screen items-center justify-center bg-canvas px-4">
        <div className="w-full max-w-[420px] rounded-lg border border-border bg-surface p-6 text-center">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-danger-subtle text-danger">
            <TriangleAlert size={18} />
          </div>
          <p className="text-[14px] font-semibold text-ink">Что-то пошло не так</p>
          <p className="mt-1.5 text-[12.5px] text-ink-muted">
            Интерфейс столкнулся с ошибкой и не может продолжить. Данные на сервере не пострадали — попробуйте перезагрузить страницу.
          </p>
          {this.state.error.message && (
            <p className="mt-3 rounded-md bg-surface-hover px-3 py-2 text-left text-[11.5px] text-ink-faint">{this.state.error.message}</p>
          )}
          <Button variant="primary" className="mt-4 w-full" icon={<RotateCcw size={13} />} onClick={() => window.location.reload()}>
            Перезагрузить страницу
          </Button>
        </div>
      </div>
    );
  }
}
