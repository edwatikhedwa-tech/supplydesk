import type { CampaignStatus } from '@/lib/types';

const CAMPAIGN_STATUS_META: Record<string, { label: string; tone: 'blue' | 'amber' | 'rose' | 'green' | 'ink'; description: string }> = {
  active: { label: 'Выполняется', tone: 'blue', description: 'SupplyDesk постепенно обрабатывает разрешённые письма.' },
  paused_for_review: { label: 'Ожидает подтверждения', tone: 'amber', description: 'Этап завершён — проверьте результат перед продолжением.' },
  paused_for_health: { label: 'Приостановлена из-за проблем', tone: 'rose', description: 'Система остановила новые отправки после сигнала о качестве или политике провайдера.' },
  stopped: { label: 'Остановлена', tone: 'ink', description: 'Оставшиеся письма остановлены пользователем.' },
  completed: { label: 'Завершена', tone: 'green', description: 'Для этой кампании больше нет ожидающих писем.' },
};

const CAMPAIGN_PAUSE_REASONS: Record<string, string> = {
  stage_review: 'Этап завершён и ждёт вашего подтверждения.',
  provider_spam_or_policy_rejection: 'Провайдер сообщил об ограничении политики или подозрении на нежелательную рассылку.',
  hard_bounce_detected: 'Обнаружен постоянный отказ по адресу поставщика.',
  abnormal_permanent_failure_rate: 'Доля постоянных отказов стала выше внутреннего порога.',
  delivery_unknown_rate: 'Слишком много отправок требуют ручной проверки.',
  repeated_transient_failures: 'Провайдер несколько раз подряд временно отказал в отправке.',
  authentication_failure: 'Почтовый аккаунт не прошёл проверку авторизации.',
  stopped_by_user: 'Оставшиеся письма остановлены пользователем.',
  manual_pause: 'Кампания поставлена на паузу пользователем.',
};

export function campaignStatusMeta(status: CampaignStatus | string) {
  return CAMPAIGN_STATUS_META[status] ?? { label: 'Состояние неизвестно', tone: 'ink' as const, description: 'Сервер вернул новое состояние, которое ещё не описано в интерфейсе.' };
}

export function campaignPauseReason(reason: string | null): string {
  if (!reason) return 'Причина не указана.';
  return CAMPAIGN_PAUSE_REASONS[reason] ?? reason.replace(/_/g, ' ');
}

export function statusToneClasses(tone: ReturnType<typeof campaignStatusMeta>['tone']): string {
  switch (tone) {
    case 'blue': return 'border-accent-200 bg-accent-50 text-accent-800';
    case 'amber': return 'border-amber-200 bg-amber-50 text-amber-900';
    case 'rose': return 'border-rose-200 bg-rose-50 text-rose-900';
    case 'green': return 'border-emerald-200 bg-emerald-50 text-emerald-900';
    default: return 'border-ink-200 bg-ink-100 text-ink-700';
  }
}

export function isTerminalCampaign(status: CampaignStatus | string): boolean {
  return status === 'completed' || status === 'stopped';
}
