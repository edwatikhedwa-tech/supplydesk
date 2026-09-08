import type {
  AuthUser,
  DashboardSummary,
  GlobalSupplierSummary,
  InboxConversation,
  InboxPreview,
  InboxSuggestion,
  MailMessage,
  RequestListItem,
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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers);
  if (method !== 'GET') headers.set('X-CSRF-Token', csrfToken);
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

  const response = await fetch(path, { ...options, method, headers, credentials: 'include' });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      payload && typeof payload === 'object' && 'error' in payload ? String((payload as { error: unknown }).error) : `Ошибка запроса (${response.status})`;
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
  listGlobalSuppliers: () => request<{ items: GlobalSupplierSummary[] }>('/api/global-suppliers'),

  listThreads: () => request<{ items: ThreadSummary[] }>('/api/correspondence'),
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
};
