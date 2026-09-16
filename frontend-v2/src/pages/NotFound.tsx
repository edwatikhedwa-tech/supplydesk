import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/Button';

export function NotFound() {
  const navigate = useNavigate();
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-surface text-ink-faint ring-1 ring-border-strong">
        <span className="text-[28px] font-semibold">404</span>
      </div>
      <div>
        <h1 className="text-[15px] font-semibold text-ink">Страница не найдена</h1>
        <p className="mt-1 text-[12.5px] text-ink-muted">Этого раздела нет в рабочем пространстве.</p>
      </div>
      <Button
        variant="secondary"
        size="sm"
        icon={<ArrowLeft size={13} />}
        onClick={() => navigate('/')}
      >
        Вернуться на дашборд
      </Button>
    </div>
  );
}