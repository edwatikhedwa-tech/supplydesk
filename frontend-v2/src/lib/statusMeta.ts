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
  sent: { label: 'Отправлено', tone: 'info' },
  waiting: { label: 'Ждём ответа', tone: 'warning' },
  answered: { label: 'Получен ответ', tone: 'success' },
  error: { label: 'Ошибка отправки', tone: 'danger' },
  delivery_unknown: { label: 'Статус неизвестен', tone: 'warning' },
};
