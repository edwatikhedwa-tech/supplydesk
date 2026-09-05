import type { RequestStatus } from './types';
import type { Tone } from '../components/ui/Badge';

export const requestStatusMeta: Record<RequestStatus, { label: string; tone: Tone }> = {
  draft: { label: 'Черновик', tone: 'neutral' },
  searching: { label: 'Идёт поиск', tone: 'info' },
  updating: { label: 'Ожидание ответов', tone: 'warning' },
  completed: { label: 'Завершена', tone: 'success' },
  error: { label: 'Ошибка поиска', tone: 'danger' },
};
