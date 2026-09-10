import { ArrowLeft, Ban } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { SupplierCardContent } from '../components/SupplierCardContent';
import { EmptyState } from '../components/ui/EmptyState';

export function SupplierDetail() {
  const { id } = useParams<{ id: string }>();
  const supplierId = Number(id);

  if (!id || Number.isNaN(supplierId)) {
    return <EmptyState icon={Ban} title="Некорректный номер поставщика" />;
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="flex items-center gap-2 px-4 sm:px-6 pt-5">
        <Link to="/suppliers" className="flex items-center gap-1 text-[12px] text-ink-muted hover:text-ink">
          <ArrowLeft size={13} />
          Поставщики
        </Link>
      </div>
      <SupplierCardContent supplierId={supplierId} />
    </div>
  );
}
