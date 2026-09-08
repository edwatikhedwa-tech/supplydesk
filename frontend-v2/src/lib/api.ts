import type {
  AuthUser,
  DashboardSummary,
  GlobalSupplierDetail,
  GlobalSupplierSummary,
  InboxConversation,
  InboxPreview,
  InboxSuggestion,
  LogisticsQuote,
  LogisticsQuoteCargoInput,
  MailMessage,
  MailTemplate,
  ManualLinkRequestOption,
  MessageSearchResult,
  PreflightResult,
  QueuedBulkResult,
  RequestDetail,
  RequestListItem,
  SupplierSendInput,
  Task,
  ThreadSummary,
} from './types';

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

/**
 * A 401 from any endpoint other than /api/auth/me means the session died
 * mid-use (expiry, revocation elsewhere). /api/auth/me itself never returns
 * 401 — it reports {authenticated: false} with a 200 — so this only fires
 * for a session that *was* valid and stopped being valid.
 */
let onSessionExpired: (() => void) | null = null;
export function setSessionExpiredHandler(handler: (() => void) | null) {
  onSessionExpired = handler;
}

const CSRF_ERROR_MESSAGE = 'CSRF-проверка не пройдена. Обновите страницу.';

async function request<T>(path: string, options: RequestInit = {}, retryingAfterCsrfRefresh = false): Promise<T> {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  if (method !== 'GET') headers.set('X-CSRF-Token', csrfToken);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(path, { ...options, method, headers, credentials: 'include' });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      payload && typeof payload === 'object' && 'error' in payload ? String((payload as { error: unknown }).error) : `Ошибка запроса (${response.status})`;

    // The CSRF token is derived from the session cookie. If another tab or
    // window on the same origin re-authenticated (a fresh login issues a new
    // session cookie), this tab's cached token silently goes stale even
    // though its own session is still perfectly valid - re-fetching /me picks
    // up the token for whatever session cookie is current and lets the
    // original call succeed transparently, instead of surfacing a confusing
    // "CSRF failed" error for something the user did nothing wrong to cause.
    if (response.status === 403 && message === CSRF_ERROR_MESSAGE && !retryingAfterCsrfRefresh && path !== '/api/auth/me') {
      const me = await request<MeResponse>('/api/auth/me').catch(() => null);
      if (me?.authenticated && me.csrf_token) {
        setCsrfToken(me.csrf_token);
        return request<T>(path, options, true);
      }
    }

    if (response.status === 401 && path !== '/api/auth/me') onSessionExpired?.();
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
  me: () => request<MeResponse>('/api/auth/me'),
  login: (email: string, password: string) =>
    request<{ authenticated: true; csrf_token: string; user: AuthUser }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' }),

  dashboardSummary: () => request<DashboardSummary>('/api/dashboard/summary'),
  listTasks: () => request<{ items: Task[] }>('/api/tasks'),
  createTask: (input: { title: string; due_date?: string; request_id?: number; supplier_id?: number }) =>
    request<{ ok: true; task_id: number }>('/api/tasks', { method: 'POST', body: JSON.stringify(input) }),
  setTaskDone: (taskId: number, done: boolean) =>
    request<{ ok: true; id: number; done: boolean }>(`/api/tasks/${taskId}/done`, { method: 'POST', body: JSON.stringify({ done }) }),
  deleteTask: (taskId: number) => request<{ ok: true }>(`/api/tasks/${taskId}`, { method: 'DELETE' }),
  listRequests: () => request<{ items: RequestListItem[] }>('/api/requests'),
  getRequestDetail: (requestId: number) => request<RequestDetail>(`/api/requests/${requestId}`),
  markSupplierIrrelevant: (requestId: number, supplierId: number) =>
    request<{ ok: true }>(`/api/requests/${requestId}/suppliers/${supplierId}/irrelevant`, { method: 'POST' }),
  createRequest: (input: { name: string; description?: string; deadline?: string; search_depth?: number; positions: { name: string }[] }) =>
    request<{ ok: true; request_id: number }>('/api/requests', { method: 'POST', body: JSON.stringify(input) }),
  startRequestSearch: (id: number) => request<{ ok: true }>(`/api/requests/${id}/search`, { method: 'POST' }),
  mailTemplate: () => request<MailTemplate>('/api/mail/template'),
  preflightBulk: (input: {
    request_id: number;
    suppliers: SupplierSendInput[];
    subject: string;
    body_text: string;
    manual_stage_approval?: boolean;
    allow_repeat?: boolean;
  }) => request<PreflightResult>('/api/mail/deliverability/preflight', { method: 'POST', body: JSON.stringify(input) }),
  sendMailBulk: (input: {
    request_id: number;
    suppliers: SupplierSendInput[];
    subject: string;
    body_text: string;
    idempotency_key: string;
    manual_stage_approval?: boolean;
    allow_repeat?: boolean;
  }) => request<{ ok: true; queued: QueuedBulkResult[] }>('/api/mail/send-bulk', { method: 'POST', body: JSON.stringify(input) }),
  listGlobalSuppliers: () => request<{ items: GlobalSupplierSummary[] }>('/api/global-suppliers'),
  getGlobalSupplierDetail: (id: number) => request<GlobalSupplierDetail>(`/api/global-suppliers/${id}`),
  saveGlobalSupplierNote: (id: number, note: string) =>
    request<{ ok: true }>(`/api/global-suppliers/${id}`, { method: 'POST', body: JSON.stringify({ note }) }),
  setGlobalSupplierRelationship: (id: number, status: 'none' | 'favorite' | 'blacklisted', reason = '') =>
    request<{ ok: true }>(`/api/global-suppliers/${id}/relationship`, { method: 'POST', body: JSON.stringify({ status, reason }) }),

  listThreads: () => request<{ items: ThreadSummary[] }>('/api/correspondence'),
  searchMessages: (q: string) => request<{ items: MessageSearchResult[] }>(`/api/mail/search?q=${encodeURIComponent(q)}`),
  threadMessages: (requestId: number, supplierId: number) =>
    request<{ items: MailMessage[] }>(`/api/mail/threads?request_id=${requestId}&supplier_id=${supplierId}`),
  sendMail: (input: { request_id: number; supplier: { id?: number; email: string; name?: string; host?: string; external_key?: string }; subject: string; body_text: string }) =>
    request<{ ok: true; queued: unknown[] }>('/api/mail/send', { method: 'POST', body: JSON.stringify(input) }),

  listInboxPreview: () => request<{ items: InboxPreview[] }>('/api/mail/inbox/preview'),
  inboxConversation: (inboxMessageId: number) =>
    request<InboxConversation>(`/api/mail/inbox/conversation?inbox_message_id=${inboxMessageId}`),
  inboxSuggestions: (inboxMessageId: number) =>
    request<{ items: InboxSuggestion[] }>(`/api/mail/inbox/${inboxMessageId}/suggestions`),
  attachInboxMessage: (input: { inbox_message_id: number; request_id: number; supplier_id: number }) =>
    request<{ message_id: number; thread_id: number; request_id: number; supplier_id: number }>('/api/mail/inbox/attach', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  ignoreInboxMessage: (inboxMessageId: number) =>
    request<{ ok: true; inbox_message_id: number }>('/api/mail/inbox/ignore', {
      method: 'POST',
      body: JSON.stringify({ inbox_message_id: inboxMessageId }),
    }),
  manualLinkInboxMessage: (input: { inbox_message_id: number; request_id: number; supplier_id?: number | null; confirmed: true }) =>
    request<{ ok: true; inbox_message_id: number; request_id: number; supplier_id: number | null }>('/api/mail/inbox/manual-link', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  listManualLinkRequests: (search: string) =>
    request<{ items: ManualLinkRequestOption[] }>(`/api/mail/inbox/requests?q=${encodeURIComponent(search)}`),
  replyToInbox: (input: { inbox_message_id: number; subject: string; body_text: string }) =>
    request<{ ok: true }>('/api/mail/inbox/reply', { method: 'POST', body: JSON.stringify(input) }),

  getAiChatUsage: () => request<{ spent_rub: number; limit_rub: number }>('/api/ai/chat/usage'),
  sendAiChatMessage: (message: string, context: string) =>
    request<{ status: string; reply: string | null; spent_rub: number; limit_rub: number; message: string }>('/api/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ message, context }),
    }),

  getThreadNote: (requestId: number, supplierId: number) => request<{ note: string }>(`/api/requests/${requestId}/suppliers/${supplierId}/note`),
  saveThreadNote: (requestId: number, supplierId: number, note: string) =>
    request<{ ok: true; note: string }>(`/api/requests/${requestId}/suppliers/${supplierId}/note`, {
      method: 'POST',
      body: JSON.stringify({ note }),
    }),

  getLogisticsQuote: (requestId: number, supplierId: number) =>
    request<{ quote: LogisticsQuote | null }>(`/api/requests/${requestId}/suppliers/${supplierId}/logistics`),
  calculateLogisticsQuote: (requestId: number, supplierId: number, input: { route_from: string; route_to: string; cargo: LogisticsQuoteCargoInput }) =>
    request<{ quote: LogisticsQuote; message: string }>(`/api/requests/${requestId}/suppliers/${supplierId}/logistics`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
};
