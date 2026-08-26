import type {
  AuthUser,
  BlacklistEntry,
  DashboardSummary,
  GlobalSupplierDetail,
  GlobalSupplierSummary,
  InboxMessage,
  MailMessage,
  RelationshipStatus,
  RequestDetail,
  RequestListItem,
  Supplier,
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
  me: () => request<MeResponse>('/api/auth/me'),
  login: (email: string, password: string) =>
    request<{ authenticated: true; csrf_token: string; user: AuthUser }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' }),

  dashboardSummary: () => request<DashboardSummary>('/api/dashboard/summary'),

  listRequests: () => request<{ items: RequestListItem[] }>('/api/requests'),
  getRequest: (id: number) => request<RequestDetail>(`/api/requests/${id}`),
  createRequest: (input: { name: string; description?: string; deadline?: string; positions: { name: string; quantity?: string }[] }) =>
    request<{ ok: true; request_id: number }>('/api/requests', { method: 'POST', body: JSON.stringify(input) }),
  updateRequest: (id: number, input: { name?: string; description?: string; deadline?: string }) =>
    request<{ ok: true }>(`/api/requests/${id}`, { method: 'POST', body: JSON.stringify(input) }),
  startRequestSearch: (id: number) => request<{ ok: true }>(`/api/requests/${id}/search`, { method: 'POST' }),
  setSupplierIrrelevant: (requestId: number, supplierId: number, value: boolean) =>
    request<{ ok: true }>(`/api/requests/${requestId}/suppliers/${supplierId}/irrelevant`, {
      method: 'POST',
      body: JSON.stringify({ value }),
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
  threadMessages: (requestId: number, supplierId: number) =>
    request<{ items: MailMessage[] }>(`/api/mail/threads?request_id=${requestId}&supplier_id=${supplierId}`),
  listInbox: () => request<{ items: InboxMessage[] }>('/api/mail/inbox'),
  inboxConversation: (inboxMessageId: number) => request<{ items: MailMessage[] }>(`/api/mail/inbox/conversation?inbox_message_id=${inboxMessageId}`),

  sendMail: (input: { request_id: number; supplier: { id: number; email: string; name?: string }; subject: string; body: string }) =>
    request<{ ok: true; queued: unknown[] }>('/api/mail/send', { method: 'POST', body: JSON.stringify(input) }),
  sendMailBulk: (input: { request_id: number; suppliers: { id: number; email: string; name?: string }[]; subject: string; body: string }) =>
    request<{ ok: true; queued: unknown[] }>('/api/mail/send-bulk', { method: 'POST', body: JSON.stringify(input) }),
  replyToInbox: (input: { inbox_message_id: number; subject: string; body: string }) =>
    request<{ ok: true }>('/api/mail/inbox/reply', { method: 'POST', body: JSON.stringify(input) }),

  mailStatus: () =>
    request<{ connected: boolean; provider?: string; email?: string; status?: string; last_error?: string | null; updated_at?: string | null }>('/api/mail/status'),
  mailTest: () => request<{ ok: true; message: string }>('/api/mail/test', { method: 'POST' }),
  mailSync: () => request<{ imported?: number } & Record<string, unknown>>('/api/mail/sync', { method: 'POST' }),
  mailDisconnect: () => request<{ ok: true }>('/api/mail/disconnect', { method: 'POST' }),

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
