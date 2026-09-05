import { isUiPreviewMode, previewDetailFor, previewRequests, previewUser } from '@/lib/previewFixtures';
import { getSupabaseAccessToken } from '@/lib/supabase';
import type {
  AuthUser,
  BlacklistEntry,
  DashboardSummary,
  GlobalSupplierDetail,
  GlobalSupplierSummary,
  InboxMessage,
  InboxConversation,
  InboxPreview,
  InboxSuggestion,
  LogisticsQuote,
  ManualLinkRequestOption,
  MailMessage,
  MailTemplate,
  CampaignSummary,
  CampaignContinuationDryRun,
  CampaignContinuationApplyResult,
  CampaignContinuationTarget,
  CrossProviderRetryApplyResult,
  CrossProviderRetryPreview,
  MailAccount,
  PreflightResult,
  QueuedBulkResult,
  RelationshipStatus,
  RequestDetail,
  RequestListItem,
  Supplier,
  SupplierSendInput,
  ThreadSummary,
} from '@/lib/types';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let csrfToken = '';

export function setCsrfToken(token: string) {
  csrfToken = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  if (method !== 'GET') {
    headers.set('X-CSRF-Token', csrfToken);
  }
  const accessToken = await getSupabaseAccessToken();
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(path, {
    ...options,
    method,
    headers,
    credentials: 'include',
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message = payload && typeof payload === 'object' && 'error' in payload ? String(payload.error) : `Ошибка запроса (${response.status})`;
    throw new ApiError(response.status, message);
  }

  return payload as T;
}

export interface MeResponse {
  authenticated: boolean;
  csrf_token?: string;
  user?: AuthUser;
}

export const api = {
  me: async (): Promise<MeResponse> => (isUiPreviewMode ? { authenticated: true, csrf_token: '', user: previewUser } : request<MeResponse>('/api/auth/me')),
  login: (email: string, password: string) =>
    request<{ authenticated: true; csrf_token: string; user: AuthUser }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' }),

  dashboardSummary: () => request<DashboardSummary>('/api/dashboard/summary'),
  stepEnrichment: () =>
    request<{ ok: true; processed: boolean; status: string }>('/api/enrichment/step', { method: 'POST' }),

  listRequests: () => (isUiPreviewMode ? Promise.resolve({ items: previewRequests }) : request<{ items: RequestListItem[] }>('/api/requests')),
  getRequest: (id: number) => (isUiPreviewMode ? Promise.resolve(previewDetailFor(id)) : request<RequestDetail>(`/api/requests/${id}`)),
  createRequest: (input: { name: string; description?: string; deadline?: string; search_depth?: number; positions: { name: string; quantity?: string }[] }) =>
    request<{ ok: true; request_id: number }>('/api/requests', { method: 'POST', body: JSON.stringify(input) }),
  deleteRequest: (id: number) => request<{ ok: true }>(`/api/requests/${id}`, { method: 'DELETE' }),
  updateRequest: (id: number, input: { name?: string; description?: string; deadline?: string }) =>
    request<{ ok: true }>(`/api/requests/${id}`, { method: 'POST', body: JSON.stringify(input) }),
  startRequestSearch: (id: number) => request<{ ok: true }>(`/api/requests/${id}/search`, { method: 'POST' }),
  stepRequestSearch: (id: number) =>
    request<{ ok: true; processed: boolean; status: string }>(`/api/requests/${id}/search/step`, { method: 'POST' }),
  setSupplierIrrelevant: (requestId: number, supplierId: number, value: boolean) =>
    request<{ ok: true }>(`/api/requests/${requestId}/suppliers/${supplierId}/irrelevant`, {
      method: 'POST',
      body: JSON.stringify({ value }),
    }),
  updateSupplierInn: (requestId: number, supplierId: number, inn: string) =>
    request<{
      ok: true;
      inn: string;
      inn_source: 'manual';
      checko_status: 'loaded' | 'not_found' | 'unavailable';
      checko_error?: string;
      global_supplier_id: number | null;
    }>(`/api/requests/${requestId}/suppliers/${supplierId}/inn`, {
      method: 'POST',
      body: JSON.stringify({ inn }),
    }),
  getLogisticsQuote: (requestId: number, supplierId: number) =>
    request<{ quote: LogisticsQuote | null }>(`/api/requests/${requestId}/suppliers/${supplierId}/logistics`),
  calculateLogistics: (
    requestId: number,
    supplierId: number,
    input: {
      route_from: string;
      route_to: string;
      cargo: { places: number; weight_kg: number; volume_m3: number; max_length_cm: number; max_width_cm: number; max_height_cm: number };
    },
  ) =>
    request<{ quote: LogisticsQuote; message: string }>(`/api/requests/${requestId}/suppliers/${supplierId}/logistics`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  listSuppliers: (params: { requestId?: number; query?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.requestId) search.set('request_id', String(params.requestId));
    if (params.query) search.set('q', params.query);
    const qs = search.toString();
    return request<{ items: Supplier[] }>(`/api/suppliers${qs ? `?${qs}` : ''}`);
  },

  listBlacklist: () => request<{ items: BlacklistEntry[] }>('/api/blacklist'),
  addBlacklist: (input: { external_key: string; company_name: string; reason: string; supplier_id?: number }) =>
    request<{ ok: true; entry_id: number }>('/api/blacklist', { method: 'POST', body: JSON.stringify(input) }),
  restoreBlacklist: (entryId: number) => request<{ ok: true }>(`/api/blacklist/${entryId}/restore`, { method: 'POST' }),

  listThreads: () => request<{ items: ThreadSummary[] }>('/api/correspondence'),
  listOutboxThreads: () => request<{ items: ThreadSummary[] }>('/api/mail/queue/messages'),
  updateThreadMetadata: (
    requestId: number,
    supplierId: number,
    input: { important?: boolean; priority?: 1 | 2 | 3 | null },
  ) => request<{
    ok: true;
    request_id: number;
    supplier_id: number;
    is_important: boolean;
    priority: 1 | 2 | 3 | null;
  }>('/api/correspondence/metadata', {
    method: 'POST',
    body: JSON.stringify({ request_id: requestId, supplier_id: supplierId, ...input }),
  }),
  threadMessages: (requestId: number, supplierId: number) =>
    request<{ items: MailMessage[] }>(`/api/mail/threads?request_id=${requestId}&supplier_id=${supplierId}`),
  listInbox: () => request<{ items: InboxMessage[] }>('/api/mail/inbox'),
  manualLinkRequests: (query = '') => {
    const params = new URLSearchParams();
    if (query.trim()) params.set('q', query.trim());
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return request<{ items: ManualLinkRequestOption[] }>(`/api/mail/inbox/requests${suffix}`);
  },
  /** Превью для дашборда — без тела письма, только для показа списка карточек. */
  listInboxPreview: () => request<{ items: InboxPreview[] }>('/api/mail/inbox/preview'),
  inboxConversation: (inboxMessageId: number) => request<InboxConversation>(`/api/mail/inbox/conversation?inbox_message_id=${inboxMessageId}`),

  sendMail: (input: { request_id: number; supplier: SupplierSendInput; subject: string; body_text: string; body_html?: string; idempotency_key?: string; allow_repeat?: boolean; mail_account_id?: number }) =>
    request<{ ok: true; queued: unknown[] }>('/api/mail/send', { method: 'POST', body: JSON.stringify(input) }),
  sendMailBulk: (input: {
    request_id: number;
    // id необязателен: получателем может быть адрес, введённый вручную, для
    // которого поставщика ещё нет — бэкенд заведёт его по адресу.
    suppliers: SupplierSendInput[];
    subject: string;
    body_text: string;
    body_html?: string;
    attachments?: { filename: string; mime_type: string; content_base64: string }[];
    idempotency_key: string;
    manual_stage_approval?: boolean;
    allow_repeat?: boolean;
    mail_account_id?: number;
  }) =>
    request<{ ok: true; queued: QueuedBulkResult[] }>('/api/mail/send-bulk', { method: 'POST', body: JSON.stringify(input) }),
  preflightBulk: (input: {
    request_id: number;
    suppliers: SupplierSendInput[];
    subject: string;
    body_text: string;
    body_html?: string;
    attachments?: { filename: string; mime_type: string; content_base64: string }[];
    manual_stage_approval?: boolean;
    allow_repeat?: boolean;
    mail_account_id?: number;
  }) => request<PreflightResult>('/api/mail/deliverability/preflight', { method: 'POST', body: JSON.stringify(input) }),
  previewBulk: (input: {
    request_id: number;
    suppliers: SupplierSendInput[];
    subject: string;
    body_text: string;
    body_html?: string;
    attachments?: { filename: string; mime_type: string; content_base64: string }[];
    manual_stage_approval?: boolean;
    allow_repeat?: boolean;
    mail_account_id?: number;
  }) => request<PreflightResult>('/api/mail/deliverability/preview', { method: 'POST', body: JSON.stringify(input) }),
  getCampaign: (campaignId: number) => request<CampaignSummary>(`/api/mail/campaigns/${campaignId}`),
  pauseCampaign: (campaignId: number) => request<CampaignSummary & { ok: true }>(`/api/mail/campaigns/${campaignId}/pause`, { method: 'POST', body: JSON.stringify({ reason: 'manual_pause' }) }),
  resumeCampaign: (campaignId: number) => request<CampaignSummary & { ok: true }>(`/api/mail/campaigns/${campaignId}/resume`, { method: 'POST', body: JSON.stringify({}) }),
  stopCampaign: (campaignId: number) => request<CampaignSummary & { ok: true }>(`/api/mail/campaigns/${campaignId}/stop`, { method: 'POST', body: JSON.stringify({}) }),
  continuationDryRun: (campaignId: number, mailAccountId: number) =>
    request<CampaignContinuationDryRun>(`/api/mail/campaigns/${campaignId}/continuation-dry-run`, { method: 'POST', body: JSON.stringify({ mail_account_id: mailAccountId }) }),
  continuationApply: (campaignId: number, input: {
    mail_account_id: number;
    limit: number;
    idempotency_key: string;
    selection_fingerprint: string;
    selected_targets: CampaignContinuationTarget[];
    operator_confirmed: true;
  }) => request<CampaignContinuationApplyResult>(
    `/api/mail/campaigns/${campaignId}/continuation-apply`,
    { method: 'POST', body: JSON.stringify(input) },
  ),
  crossProviderRetryPreview: (input: {
    request_id: number;
    original_job_id: number;
    original_message_id: number;
    original_attempt_id?: number;
    mail_account_id: number;
  }) => request<CrossProviderRetryPreview>('/api/mail/cross-provider-retry/preview', {
    method: 'POST', body: JSON.stringify(input),
  }),
  crossProviderRetryApply: (input: {
    request_id: number;
    original_job_id: number;
    original_message_id: number;
    original_attempt_id?: number;
    mail_account_id: number;
    idempotency_key: string;
    selection_fingerprint: string;
    operator_confirmed: true;
    confirmation: {
      recipient_masked: string;
      original_provider: 'yandex';
      original_smtp_code: number;
      target_provider: 'mailru';
      reason: 'proven_provider_rejection';
    };
  }) => request<CrossProviderRetryApplyResult>('/api/mail/cross-provider-retry/apply', {
    method: 'POST', body: JSON.stringify(input),
  }),
  /** Куда, вероятно, относится неразобранное письмо (по адресу отправителя). */
  inboxSuggestions: (inboxMessageId: number) =>
    request<{ items: InboxSuggestion[] }>(`/api/mail/inbox/${inboxMessageId}/suggestions`),
  /** Привязать письмо к заявке вручную — когда поставщик написал новое письмо,
   *  а не ответил на наше, и автоматическое сопоставление не сработало. */
  attachInboxMessage: (input: { inbox_message_id: number; request_id: number; supplier_id: number }) =>
    request<{ message_id: number; thread_id: number; request_id: number; supplier_id: number }>(
      '/api/mail/inbox/attach', { method: 'POST', body: JSON.stringify(input) }),
  manuallyLinkInboxMessage: (input: { inbox_message_id: number; request_id: number; supplier_id?: number | null; confirmed: true }) =>
    request<{ ok: true; inbox_message_id: number; request_id: number; supplier_id: number | null; source: 'manual' }>(
      '/api/mail/inbox/manual-link', { method: 'POST', body: JSON.stringify(input) }),
  unlinkManualInboxMessage: (inboxMessageId: number) =>
    request<{ ok: true; already_unlinked: boolean; inbox_message_id: number }>(
      '/api/mail/inbox/manual-unlink', { method: 'POST', body: JSON.stringify({ inbox_message_id: inboxMessageId }) }),
  replyToInbox: (input: { inbox_message_id: number; subject: string; body_text: string; body_html?: string }) =>
    request<{ ok: true }>('/api/mail/inbox/reply', { method: 'POST', body: JSON.stringify(input) }),
  verifyDelivery: (messageId: number) =>
    request<{ outcome: string; status: string; message_id: number }>(`/api/mail/messages/${messageId}/verify`, { method: 'POST', body: JSON.stringify({}) }),
  resendDelivery: (messageId: number, confirmed = false) =>
    request<{ ok: true; resent: boolean; requires_confirmation?: boolean; warning?: string; outcome?: string; message_id?: number }>(
      `/api/mail/messages/${messageId}/resend`, { method: 'POST', body: JSON.stringify({ confirmed }) }),
  resolveDelivery: (messageId: number, comment = '') =>
    request<{ ok: true; already_resolved: boolean; resolved_at?: string }>(
      `/api/mail/messages/${messageId}/resolve`, { method: 'POST', body: JSON.stringify({ comment }) }),

  mailStatus: () =>
    request<{ connected: boolean; provider?: string; email?: string; status?: string; last_error?: string | null; updated_at?: string | null; accounts?: MailAccount[] }>('/api/mail/status'),
  mailAccounts: () => request<{ items: MailAccount[] }>('/api/mail/accounts'),
  mailTemplate: () => request<MailTemplate>('/api/mail/template'),
  saveMailTemplate: (input: Pick<MailTemplate, 'subject' | 'body' | 'attachments'>) =>
    request<{ ok: true } & MailTemplate>('/api/mail/template', { method: 'POST', body: JSON.stringify(input) }),
  mailConnectMailru: (email: string, appPassword: string) => request<{ ok: true; account: MailAccount }>('/api/mail/accounts/mailru/connect', { method: 'POST', body: JSON.stringify({ email, app_password: appPassword }) }),
  mailTest: (mailAccountId?: number) => request<{ ok: true; message: string }>('/api/mail/test', { method: 'POST', body: JSON.stringify(mailAccountId == null ? {} : { mail_account_id: mailAccountId }) }),
  mailTestAccount: (mailAccountId: number) => request<{ ok: true; message: string }>(`/api/mail/accounts/${mailAccountId}/test`, { method: 'POST', body: JSON.stringify({}) }),
  mailSync: (mailAccountId?: number) => request<{ imported?: number } & Record<string, unknown>>('/api/mail/sync', { method: 'POST', body: JSON.stringify(mailAccountId == null ? {} : { mail_account_id: mailAccountId }) }),
  mailDisconnect: (mailAccountId?: number) => request<{ ok: true }>('/api/mail/disconnect', { method: 'POST', body: JSON.stringify(mailAccountId == null ? {} : { mail_account_id: mailAccountId }) }),
  mailDisconnectAccount: (mailAccountId: number) => request<{ ok: true }>(`/api/mail/accounts/${mailAccountId}`, { method: 'DELETE' }),

  listGlobalSuppliers: () => request<{ items: GlobalSupplierSummary[] }>('/api/global-suppliers'),
  globalSupplierDetail: (id: number) => request<GlobalSupplierDetail>(`/api/global-suppliers/${id}`),
  updateGlobalSupplierNote: (id: number, note: string) =>
    request<{ ok: true }>(`/api/global-suppliers/${id}`, { method: 'POST', body: JSON.stringify({ note }) }),
  setGlobalSupplierRelationship: (id: number, status: RelationshipStatus, reason?: string) =>
    request<{ ok: true }>(`/api/global-suppliers/${id}/relationship`, { method: 'POST', body: JSON.stringify({ status, reason }) }),
  reportGlobalSupplierIssue: (id: number, input: { reason: string; comment?: string; correct_inn?: string; blacklist?: boolean }) =>
    request<{ ok: true; issue_id: number }>(`/api/global-suppliers/${id}/issues`, { method: 'POST', body: JSON.stringify(input) }),
  setDealRating: (requestId: number, supplierId: number, rating: number) =>
    request<{ ok: true }>(`/api/requests/${requestId}/suppliers/${supplierId}/rating`, { method: 'POST', body: JSON.stringify({ rating }) }),
};
