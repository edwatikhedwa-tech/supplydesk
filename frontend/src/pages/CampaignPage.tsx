import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, ArrowLeft, CheckCircle2, ChevronRight, CircleStop, Clock3, Loader2, Pause, Play, RefreshCw, ShieldAlert, Square } from 'lucide-react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ApiError, api } from '@/lib/api';
import { campaignPauseReason, campaignStatusMeta, isTerminalCampaign, statusToneClasses } from '@/lib/campaign';
import type { CampaignContinuationDryRun, CampaignSummary, MailAccount, RequestDetail } from '@/lib/types';

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

function formatRate(value: number | undefined): string {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function providerLabel(provider: string): string {
  return provider === 'yandex' ? 'Yandex' : provider === 'mailru' ? 'Mail.ru' : provider;
}

export function CampaignPage() {
  const { id } = useParams<{ id: string }>();
  const campaignId = id ? Number(id) : NaN;
  const [summary, setSummary] = useState<CampaignSummary | null>(null);
  const [request, setRequest] = useState<RequestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [actionLoading, setActionLoading] = useState<'pause' | 'resume' | 'stop' | null>(null);
  const [confirmAction, setConfirmAction] = useState<'resume' | 'stop' | null>(null);
  const [mailAccounts, setMailAccounts] = useState<MailAccount[]>([]);
  const [continuation, setContinuation] = useState<CampaignContinuationDryRun | null>(null);
  const [continuationLoading, setContinuationLoading] = useState(false);
  const [continuationError, setContinuationError] = useState('');

  const load = useCallback(async (initial = false) => {
    if (initial) setLoading(true); else setRefreshing(true);
    setError('');
    try {
      const next = await api.getCampaign(campaignId);
      setSummary(next);
      const [requestResult] = await Promise.allSettled([api.getRequest(next.request_id)]);
      if (requestResult.status === 'fulfilled') setRequest(requestResult.value);
    } catch (requestError) {
      setError(requestError instanceof ApiError ? requestError.message : 'Не удалось загрузить состояние кампании.');
    } finally {
      if (initial) setLoading(false); else setRefreshing(false);
    }
  }, [campaignId]);

  useEffect(() => {
    if (Number.isNaN(campaignId)) return;
    void load(true);
  }, [campaignId, load]);

  useEffect(() => {
    void api.mailAccounts().then((result) => setMailAccounts(result.items ?? [])).catch(() => setMailAccounts([]));
  }, []);

  useEffect(() => {
    if (!summary || isTerminalCampaign(summary.status)) return undefined;
    const interval = summary.status === 'active' ? 4000 : 15000;
    const timer = window.setInterval(() => void load(), interval);
    return () => window.clearInterval(timer);
  }, [summary, load]);

  if (Number.isNaN(campaignId)) return <Navigate to="/requests" replace />;
  if (loading) return <CampaignSkeleton />;
  if (!summary) return <CampaignError message={error || 'Кампания не найдена.'} onRetry={() => void load(true)} />;

  const title = request?.request.name ?? `Кампания №${summary.campaign_id}`;
  const canAct = !isTerminalCampaign(summary.status);
  const stageComplete = summary.status === 'paused_for_review' && summary.pause_reason === 'stage_review';
  const manualPaused = summary.status === 'paused_for_review' && summary.pause_reason !== 'stage_review';
  const healthPaused = summary.status === 'paused_for_health';
  const meta = manualPaused
    ? { label: 'Кампания на паузе', tone: 'amber' as const, description: 'Текущий этап сохранён. Продолжите его, когда будете готовы.' }
    : campaignStatusMeta(summary.status);
  const progressDenominator = Math.max(summary.planned, 1);
  const progressValue = Math.min(100, Math.round(((summary.accepted + summary.failed_permanent + summary.failed_transient + summary.delivery_unknown + summary.cancelled) / progressDenominator) * 100));
  const mailruAccounts = mailAccounts.filter((account) => account.provider === 'mailru' && account.connected && account.outgoing_enabled);

  const runContinuationDryRun = async () => {
    const target = mailruAccounts[0];
    if (!target) {
      setContinuationError('Сначала подключите Mail.ru в Настройках.');
      return;
    }
    setContinuationLoading(true); setContinuationError(''); setContinuation(null);
    try {
      setContinuation(await api.continuationDryRun(campaignId, target.id));
    } catch (requestError) {
      setContinuationError(requestError instanceof ApiError ? requestError.message : 'Не удалось подготовить безопасную проверку.');
    } finally { setContinuationLoading(false); }
  };

  const runAction = async (action: 'pause' | 'resume' | 'stop') => {
    setActionLoading(action); setActionError(''); setActionMessage('');
    try {
      const next = action === 'pause' ? await api.pauseCampaign(campaignId) : action === 'resume' ? await api.resumeCampaign(campaignId) : await api.stopCampaign(campaignId);
      setSummary(next);
      setActionMessage(action === 'pause' ? 'Кампания поставлена на паузу.' : action === 'resume' ? (manualPaused ? 'Текущий этап продолжен.' : healthPaused ? 'Кампания продолжена после проверки.' : 'Следующий этап разрешён.') : 'Оставшиеся письма остановлены.');
      setConfirmAction(null);
    } catch (requestError) {
      setActionError(requestError instanceof ApiError ? requestError.message : 'Действие не выполнено. Состояние кампании не изменено в интерфейсе.');
    } finally { setActionLoading(null); }
  };

  return <div className="campaign-page min-h-screen bg-ink-50 px-4 py-6 sm:px-6 lg:px-10 lg:py-9">
    <div className="mx-auto max-w-[1400px] space-y-5">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <nav className="mb-3 flex items-center gap-1.5 text-xs text-ink-500"><Link to={request ? `/requests/${request.request.id}` : '/requests'} className="hover:text-ink-800">Заявка</Link><ChevronRight className="h-3 w-3 text-ink-300" /><span className="truncate font-medium text-ink-700">Кампания</span></nav>
          <div className="flex flex-wrap items-center gap-2"><h1 className="break-words text-page-title font-bold tracking-tight text-ink-900">{title}</h1><span className="rounded-full bg-ink-100 px-2.5 py-1 text-xs font-bold text-ink-600">Кампания №{summary.campaign_id}</span></div>
          <p className="mt-2 text-sm text-ink-500">{summary.provider} · обновлено {formatDate(summary.updated_at)} · этап {summary.stage}</p>
        </div>
        <button type="button" onClick={() => void load()} disabled={refreshing} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-ink-200 bg-white px-3 text-sm font-semibold text-ink-700 shadow-soft hover:border-accent-300 hover:text-accent-700 disabled:cursor-wait disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />Обновить</button>
      </header>

      <section aria-live="polite" className={`rounded-2xl border p-4 sm:p-5 ${statusToneClasses(meta.tone)}`}><div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"><div className="flex min-w-0 items-start gap-3"><div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/75">{meta.tone === 'green' ? <CheckCircle2 className="h-5 w-5" /> : meta.tone === 'rose' ? <ShieldAlert className="h-5 w-5" /> : meta.tone === 'amber' ? <Clock3 className="h-5 w-5" /> : <Play className="h-5 w-5" />}</div><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-bold">{meta.label}</h2><span className="rounded-full bg-white/75 px-2 py-0.5 text-2xs font-bold uppercase tracking-wider">{summary.status}</span></div><p className="mt-1 max-w-2xl text-sm leading-6 opacity-85">{meta.description}</p>{summary.pause_reason && <p className="mt-2 text-sm font-semibold">Причина: {campaignPauseReason(summary.pause_reason)}</p>}</div></div><div className="min-w-[220px] lg:w-72"><div className="flex items-center justify-between text-xs font-semibold"><span>Общий прогресс</span><span>{progressValue}%</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-black/10"><div className="h-full rounded-full bg-current transition-all" style={{ width: `${progressValue}%` }} /></div><p className="mt-2 text-xs opacity-75">Осталось: <span className="font-bold">{summary.remaining}</span></p></div></div></section>

      {summary.provider_warning && <div role="status" className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" /><div><p className="font-bold">Ограничение провайдера</p><p className="mt-1 leading-6">{summary.provider_warning}</p><p className="mt-1 text-xs text-amber-900/80">Внутренние интервалы SupplyDesk не гарантируют доставку или попадание во «Входящие».</p></div></div>}

      {summary.provider === 'yandex' && summary.remaining > 0 && !isTerminalCampaign(summary.status) && <section className="rounded-2xl border border-accent-200 bg-accent-50/60 p-4 sm:p-5"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-2xs font-bold uppercase tracking-[0.15em] text-accent-700">Безопасная подготовка</p><h2 className="mt-1 text-lg font-bold text-ink-900">Продолжение через Mail.ru</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-ink-700">Проверка покажет только непредпринятые получатели. Уже принятые, failed и delivery_unknown письма повторно не включаются.</p></div><button type="button" onClick={() => void runContinuationDryRun()} disabled={continuationLoading || mailruAccounts.length === 0} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg bg-accent-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-50">{continuationLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldAlert className="h-4 w-4" />}Проверить без отправки</button></div>{mailruAccounts.length === 0 && <p className="mt-3 text-xs font-semibold text-amber-800">Подключите Mail.ru в Настройках, чтобы подготовить dry-run.</p>}{continuationError && <p role="alert" className="mt-3 text-xs font-semibold text-rose-700">{continuationError}</p>}{continuation && <div className="mt-4 grid gap-2 sm:grid-cols-4"><div className="rounded-xl border border-emerald-200 bg-white px-3 py-3"><p className="text-2xs font-semibold text-ink-500">Будет подготовлено</p><p className="mt-1 text-xl font-bold text-emerald-700">{continuation.would_create}</p></div><div className="rounded-xl border border-ink-200 bg-white px-3 py-3"><p className="text-2xs font-semibold text-ink-500">Уже принято · не повторять</p><p className="mt-1 text-xl font-bold text-ink-900">{continuation.accepted_not_repeated}</p></div><div className="rounded-xl border border-rose-200 bg-white px-3 py-3"><p className="text-2xs font-semibold text-ink-500">Failed · не повторять</p><p className="mt-1 text-xl font-bold text-rose-700">{continuation.failed_not_repeated}</p></div><div className="rounded-xl border border-orange-200 bg-white px-3 py-3"><p className="text-2xs font-semibold text-ink-500">Unknown · не повторять</p><p className="mt-1 text-xl font-bold text-orange-700">{continuation.delivery_unknown_not_repeated}</p></div></div>}{continuation && <p className="mt-3 text-xs font-semibold text-emerald-800">Dry-run завершён. Ничего не создано, не поставлено в очередь и не отправлено.</p>}</section>}

      <section aria-label="Показатели кампании" className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8"><CampaignMetric label="Запланировано" value={summary.planned} /><CampaignMetric label="Допущено" value={summary.eligible} /><CampaignMetric label="Исключено" value={summary.excluded} tone={summary.excluded ? 'amber' : undefined} /><CampaignMetric label="Отправлено" value={summary.accepted} tone="green" title="Почтовый сервер принял письмо. Доставка во входящие не гарантируется." /><CampaignMetric label="Постоянные отказы" value={summary.failed_permanent} tone={summary.failed_permanent ? 'red' : undefined} /><CampaignMetric label="Временные ошибки" value={summary.failed_transient} tone={summary.failed_transient ? 'amber' : undefined} /><CampaignMetric label="Требуют проверки" value={summary.delivery_unknown} tone={summary.delivery_unknown ? 'red' : undefined} title="Нельзя безопасно определить результат отправки. Повтор автоматически не выполняется." /><CampaignMetric label="Осталось" value={summary.remaining} /></section>
      {summary.accepted_by_provider && Object.keys(summary.accepted_by_provider).length > 0 && <p data-provider-neutral-accounting className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-900">Фактически принято по провайдерам: {Object.entries(summary.accepted_by_provider).map(([provider, count]) => `${providerLabel(provider)} — ${count}`).join(' · ')} · всего {summary.accepted}{summary.accepted_reconciled ? ` · подтверждено историей — ${summary.accepted_reconciled}` : ''}{summary.historical_disputed_transient ? ` · спорных временных — ${summary.historical_disputed_transient}` : ''}</p>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <section className="rounded-2xl border border-ink-200 bg-white p-4 shadow-soft sm:p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><p className="text-2xs font-bold uppercase tracking-[0.15em] text-ink-400">Rollout</p><h2 className="mt-1 text-lg font-bold text-ink-900">Путь этапов</h2><p className="mt-1 text-sm text-ink-500">Порог накопительный: 10 → 25 → 50 → все.</p></div><span className="text-sm font-bold text-accent-700">Этап {summary.stage} · до {summary.stage_limit}</span></div><div className="mt-5 grid grid-cols-4 gap-2">{[['1', '10'], ['2', '25'], ['3', '50'], ['4', 'Все']].map(([stage, limit], index) => <div key={stage} className={`relative rounded-xl border px-2 py-3 text-center ${summary.stage === Number(stage) ? 'border-accent-400 bg-accent-50' : summary.stage > Number(stage) ? 'border-emerald-200 bg-emerald-50' : 'border-ink-200 bg-ink-50'}`}><p className="text-2xs font-bold uppercase tracking-wider text-ink-400">Этап {stage}</p><p className="mt-1 text-sm font-bold text-ink-900">{limit}</p>{index < 3 && <span className="absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-ink-300 sm:block">→</span>}</div>)}</div><p className={`mt-4 flex items-start gap-2 rounded-lg px-3 py-2.5 text-xs leading-5 ${summary.manual_stage_approval ? 'bg-amber-50 text-amber-900' : 'bg-ink-50 text-ink-600'}`}><Clock3 className="mt-0.5 h-4 w-4 shrink-0" />{summary.manual_stage_approval ? 'Этапы подтверждаются вручную.' : 'Этапы продолжаются автоматически при нормальном состоянии кампании.'}</p></section>

          {manualPaused && <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 sm:p-5"><div className="flex items-start gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-amber-600"><Pause className="h-5 w-5" /></div><div className="min-w-0"><h2 className="text-lg font-bold text-amber-950">Кампания на паузе</h2><p className="mt-1 text-sm leading-6 text-amber-900">Пауза пользователя сохранит текущий этап и его лимит. Уже начатые отправки не изменяются.</p><HealthSummary summary={summary} /></div></div><button type="button" onClick={() => setConfirmAction('resume')} disabled={actionLoading !== null} className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg border border-amber-300 bg-white px-4 text-sm font-bold text-amber-900 hover:border-amber-400 hover:bg-amber-50 disabled:cursor-wait disabled:opacity-50 sm:w-auto"><Play className="h-4 w-4" />Продолжить текущий этап</button></section>}
          {stageComplete && <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 sm:p-5"><div className="flex items-start gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-amber-600"><Clock3 className="h-5 w-5" /></div><div className="min-w-0"><h2 className="text-lg font-bold text-amber-950">Этап завершён — проверьте результат</h2><p className="mt-1 text-sm leading-6 text-amber-900">После первых писем вы можете разрешить следующий накопительный этап. Повторной отправки уже обработанных писем не будет.</p><HealthSummary summary={summary} /></div></div><button type="button" onClick={() => setConfirmAction('resume')} disabled={actionLoading !== null} className="mt-4 inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 text-sm font-bold text-white hover:bg-accent-700 disabled:cursor-wait disabled:opacity-50 sm:w-auto"><Play className="h-4 w-4" />Продолжить следующий этап</button></section>}

          {healthPaused && <section className="rounded-2xl border border-rose-200 bg-rose-50/70 p-4 sm:p-5"><div className="flex items-start gap-3"><ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" /><div><h2 className="text-lg font-bold text-rose-950">Кампания остановлена</h2><p className="mt-1 text-sm leading-6 text-rose-900">{campaignPauseReason(summary.pause_reason)}</p><HealthSummary summary={summary} /></div></div><p className="mt-4 text-xs leading-5 text-rose-900/80">Сначала проверьте причину и состояние почтового аккаунта. Продолжение не выполняется автоматически.</p><button type="button" onClick={() => setConfirmAction('resume')} disabled={actionLoading !== null} className="mt-4 inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border border-rose-300 bg-white px-4 text-sm font-bold text-rose-800 hover:border-rose-400 hover:bg-rose-50 disabled:opacity-50"><Play className="h-4 w-4" />Продолжить после проверки</button></section>}

          {summary.delivery_unknown > 0 && <section className="rounded-2xl border border-orange-200 bg-orange-50/70 p-4 sm:p-5"><div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-orange-600" /><div><h2 className="text-sm font-bold text-orange-950">Есть отправки, требующие проверки · {summary.delivery_unknown}</h2><p className="mt-1 text-sm leading-6 text-orange-900">Нельзя безопасно определить, принял ли сервер эти письма. SupplyDesk не отправит их повторно автоматически.</p></div></div></section>}

          {(summary.excluded_targets?.length ?? 0) > 0 && <section className="rounded-2xl border border-ink-200 bg-white p-4 shadow-soft sm:p-5"><div className="flex items-center gap-2"><CircleStop className="h-4 w-4 text-amber-600" /><h2 className="text-sm font-bold text-ink-900">Исключённые получатели · {summary.excluded_targets?.length}</h2></div><div className="mt-3 overflow-hidden rounded-xl border border-ink-200">{summary.excluded_targets?.map((target) => <div key={`${target.email}-${target.reason}`} className="grid gap-1 border-b border-ink-100 px-3 py-3 text-xs last:border-b-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.1fr)] sm:gap-3"><span className="break-words font-semibold text-ink-800">{target.supplier_name ?? 'Контакт без карточки'}</span><span className="break-all text-ink-600">{target.email}</span><span className="break-words text-amber-800">{target.reason.replace(/_/g, ' ')}</span></div>)}</div></section>}
        </div>

        <aside className="space-y-5"><section className="rounded-2xl border border-ink-200 bg-white p-4 shadow-soft sm:p-5"><h2 className="text-sm font-bold text-ink-900">Действия</h2><p className="mt-1 text-xs leading-5 text-ink-500">Эти действия управляют только оставшимися письмами. Уже начатая необратимая отправка может завершиться.</p><div className="mt-4 space-y-2">{summary.status === 'active' && <button type="button" onClick={() => void runAction('pause')} disabled={actionLoading !== null} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-ink-200 px-3 text-sm font-bold text-ink-700 hover:border-accent-300 hover:text-accent-700 disabled:cursor-wait disabled:opacity-50">{actionLoading === 'pause' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pause className="h-4 w-4" />}Пауза</button>}{canAct && summary.remaining > 0 && <button type="button" onClick={() => setConfirmAction('stop')} disabled={actionLoading !== null} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 text-sm font-bold text-rose-700 hover:border-rose-300 hover:bg-rose-100 disabled:cursor-wait disabled:opacity-50"><Square className="h-4 w-4" />Остановить оставшиеся</button>}{summary.status === 'stopped' && <p className="rounded-lg bg-ink-50 px-3 py-3 text-xs leading-5 text-ink-600">Кампания остановлена. Возобновить её нельзя.</p>}{summary.status === 'completed' && <p className="rounded-lg bg-emerald-50 px-3 py-3 text-xs leading-5 text-emerald-800">Все доступные письма обработаны.</p>}</div>{actionMessage && <p role="status" className="mt-3 flex items-start gap-2 text-xs font-semibold text-emerald-700"><CheckCircle2 className="h-4 w-4 shrink-0" />{actionMessage}</p>}{actionError && <p role="alert" className="mt-3 flex items-start gap-2 text-xs font-semibold text-rose-700"><AlertTriangle className="h-4 w-4 shrink-0" />{actionError}</p>}</section><section className="rounded-2xl border border-ink-200 bg-white p-4 shadow-soft sm:p-5"><h2 className="text-sm font-bold text-ink-900">Состояние качества</h2><dl className="mt-4 space-y-3 text-xs"><RateRow label="Постоянные отказы" value={formatRate(summary.health.permanent_failure_rate)} /><RateRow label="Временные ошибки" value={formatRate(summary.health.transient_failure_rate)} /><RateRow label="Требуют проверки" value={formatRate(summary.health.unknown_rate)} /><RateRow label="Отказы политики" value={formatRate(summary.health.provider_rejection_rate)} /><RateRow label="Hard bounce" value={summary.health.hard_bounces} /></dl><p className="mt-4 border-t border-ink-100 pt-3 text-xs leading-5 text-ink-500">Попыток по аудиту: <span className="font-bold text-ink-700">{summary.attempted}</span>. Принято сервером — не то же самое, что доставлено.</p></section><section className="rounded-2xl border border-ink-200 bg-ink-50/70 p-4 sm:p-5"><h2 className="text-sm font-bold text-ink-900">Контекст</h2><dl className="mt-3 space-y-2 text-xs"><div className="flex justify-between gap-3"><dt className="text-ink-500">Заявка</dt><dd className="max-w-[200px] break-words text-right font-semibold text-ink-800">{title}</dd></div><div className="flex justify-between gap-3"><dt className="text-ink-500">Почтовый аккаунт</dt><dd className="text-right font-semibold text-ink-800">№{summary.mail_account_id}</dd></div><div className="flex justify-between gap-3"><dt className="text-ink-500">Обновлено</dt><dd className="text-right font-semibold text-ink-800">{formatDate(summary.updated_at)}</dd></div></dl></section></aside>
      </div>
      {error && <div role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      <Link to={request ? `/requests/${request.request.id}` : '/requests'} className="inline-flex items-center gap-2 text-sm font-semibold text-accent-700 hover:text-accent-800"><ArrowLeft className="h-4 w-4" />Вернуться к заявке</Link>
    </div>
   {confirmAction && <CampaignConfirmDialog action={confirmAction} summary={summary} resumeCurrentStage={manualPaused || healthPaused} onClose={() => setConfirmAction(null)} onConfirm={() => void runAction(confirmAction)} loading={actionLoading === confirmAction} />}
  </div>;
}

function CampaignMetric({ label, value, tone, title }: { label: string; value: number; tone?: 'green' | 'amber' | 'red'; title?: string }) {
  return <div title={title} className="rounded-xl border border-ink-200 bg-white px-3 py-3 shadow-soft"><p className="min-h-8 text-2xs font-semibold leading-4 text-ink-500">{label}</p><p className={`mt-1 text-xl font-bold tabular-nums ${tone === 'green' ? 'text-emerald-700' : tone === 'amber' ? 'text-amber-700' : tone === 'red' ? 'text-rose-700' : 'text-ink-900'}`}>{value}</p></div>;
}

function HealthSummary({ summary }: { summary: CampaignSummary }) {
  return <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-xs"><div><dt className="text-amber-900/70">Отправлено</dt><dd className="mt-0.5 font-bold text-amber-950">{summary.accepted}</dd></div><div><dt className="text-amber-900/70">Постоянных отказов</dt><dd className="mt-0.5 font-bold text-amber-950">{summary.failed_permanent}</dd></div><div><dt className="text-amber-900/70">Требуют проверки</dt><dd className="mt-0.5 font-bold text-amber-950">{summary.delivery_unknown}</dd></div><div><dt className="text-amber-900/70">Временных ошибок</dt><dd className="mt-0.5 font-bold text-amber-950">{summary.failed_transient}</dd></div></dl>;
}

function RateRow({ label, value }: { label: string; value: string | number }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-ink-500">{label}</dt><dd className="font-bold tabular-nums text-ink-800">{value}</dd></div>;
}

function CampaignConfirmDialog({ action, summary, resumeCurrentStage, onClose, onConfirm, loading }: { action: 'resume' | 'stop'; summary: CampaignSummary; resumeCurrentStage: boolean; onClose: () => void; onConfirm: () => void; loading: boolean }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const firstRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    firstRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => { if (event.key === 'Escape' && !loading) onClose(); if (event.key === 'Tab' && dialogRef.current) { const items = Array.from(dialogRef.current.querySelectorAll<HTMLElement>('button:not([disabled])')); if (items.length && event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items[items.length - 1].focus(); } else if (items.length && !event.shiftKey && document.activeElement === items[items.length - 1]) { event.preventDefault(); items[0].focus(); } } };
    window.addEventListener('keydown', handleKey);
    return () => { window.removeEventListener('keydown', handleKey); previous?.focus(); };
  }, [loading, onClose]);
  const stop = action === 'stop';
  return <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink-900/40 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget && !loading) onClose(); }}><div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="campaign-confirm-title" className="w-full max-w-md rounded-2xl border border-ink-200 bg-white p-5 shadow-panel sm:p-6"><div className={`flex h-11 w-11 items-center justify-center rounded-xl ${stop ? 'bg-rose-50 text-rose-600' : 'bg-accent-50 text-accent-600'}`}>{stop ? <ShieldAlert className="h-5 w-5" /> : <Play className="h-5 w-5" />}</div><h2 id="campaign-confirm-title" className="mt-4 text-lg font-bold text-ink-900">{stop ? 'Остановить оставшиеся письма?' : resumeCurrentStage ? 'Продолжить текущий этап?' : 'Продолжить следующий этап?'}</h2><p className="mt-2 text-sm leading-6 text-ink-600">{stop ? 'Уже отправленные письма и неопределённые отправки останутся в истории. Будут остановлены только письма, которые ещё не начали отправляться.' : resumeCurrentStage ? `Кампания продолжит текущий этап без увеличения его лимита. Сейчас осталось ${summary.remaining} писем; уже принятые и неопределённые отправки повторно не создаются.` : `Будет разрешён следующий накопительный этап. Сейчас осталось ${summary.remaining} писем; уже принятые и неопределённые отправки повторно не создаются.`}</p><div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><button type="button" onClick={onClose} disabled={loading} className="min-h-10 rounded-lg px-3 text-sm font-semibold text-ink-600 hover:bg-ink-50 disabled:opacity-50">Отмена</button><button ref={firstRef} type="button" onClick={onConfirm} disabled={loading} className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-bold text-white disabled:cursor-wait disabled:opacity-50 ${stop ? 'bg-rose-600 hover:bg-rose-700' : 'bg-accent-600 hover:bg-accent-700'}`}>{loading && <Loader2 className="h-4 w-4 animate-spin" />}{stop ? 'Остановить оставшиеся' : 'Да, продолжить'}</button></div></div></div>;
}

function CampaignSkeleton() {
  return <div className="min-h-screen bg-ink-50 px-4 py-6 sm:px-6 lg:px-10 lg:py-9"><div className="mx-auto max-w-[1400px] space-y-5"><div className="skeleton h-10 w-2/3 rounded-lg" /><div className="skeleton h-32 rounded-2xl" /><div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">{Array.from({ length: 8 }, (_, index) => <div key={index} className="skeleton h-24 rounded-xl" />)}</div><div className="skeleton h-64 rounded-2xl" /></div></div>;
}

function CampaignError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="flex min-h-screen items-center justify-center bg-ink-50 px-6 py-10"><div className="w-full max-w-md rounded-2xl border border-rose-200 bg-white p-7 text-center shadow-panel"><div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-50 text-rose-600"><AlertTriangle className="h-6 w-6" /></div><h1 className="mt-5 text-lg font-bold text-ink-900">Не удалось загрузить кампанию</h1><p className="mt-2 text-sm leading-6 text-ink-500">{message}</p><button type="button" onClick={onRetry} className="mt-6 inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-accent-700"><RefreshCw className="h-4 w-4" />Повторить</button></div></div>;
}
