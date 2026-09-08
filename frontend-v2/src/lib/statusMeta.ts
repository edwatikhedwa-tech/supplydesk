import type { RequestStatus, SupplierMailStatus } from './types';
import type { Tone } from '../components/ui/Badge';

export const requestStatusMeta: Record<RequestStatus, { label: string; tone: Tone }> = {
  draft: { label: 'Черновик', tone: 'neutral' },
  searching: { label: 'Идёт поиск', tone: 'info' },
  updating: { label: 'Ожидание ответов', tone: 'warning' },
  completed: { label: 'Завершена', tone: 'success' },
  error: { label: 'Ошибка поиска', tone: 'danger' },
};

export const supplierMailStatusMeta: Record<SupplierMailStatus, { label: string; tone: Tone }> = {
  not_sent: { label: 'Не отправлено', tone: 'neutral' },
  queued: { label: 'В очереди', tone: 'info' },
  sending: { label: 'Отправляется', tone: 'info' },
  sent: { label: 'Отправлено', tone: 'warning' },
  delivery_unknown: { label: 'Статус неизвестен', tone: 'warning' },
  failed: { label: 'Ошибка отправки', tone: 'danger' },
  cancelled: { label: 'Отменено', tone: 'neutral' },
};
