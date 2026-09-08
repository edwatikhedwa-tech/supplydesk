// Data contracts for frontend-v2, aligned 1:1 with the real backend contract
// (frontend/src/lib/api.ts + types.ts, and live-verified against a running
// LOCAL_CANONICAL backend on 2026-09-08). Fields the backend does not
// actually send were removed; UI-only derived values are computed in
// src/lib/derive.ts instead of pretending the API provides them.

export type RequestStatus = 'draft' | 'searching' | 'updating' | 'completed' | 'error';

export interface RequestListItem {
  id: number;
  name: string;
  description: string | null;
  /** Empty string means "no deadline set" — the real API never sends null here. */
  deadline: string;
  sender_name: string;
  company_name: string;
  created_at: string;
  updated_at: string | null;
  status: RequestStatus;
  search_progress: number;
  search_total: number;
  search_depth: number;
  last_error: string | null;
  positions_count: number;
  suppliers_count: number;
  sent_count: number;
  replies_count: number;
  /** Only present on the single-request detail endpoint, not the list. */
  mail_metrics?: {
    outbound_total: number;
    queued: number;
    accepted: number;
    accepted_effective: number;
    failed: number;
    delivery_unknown: number;
    bounced: number;
    cancelled: number;
    replies: number;
  };
}

export interface RequestPosition {
  id: number;
  position_key: string;
  name: string;
  quantity: string;
}

// The backend's user-facing vocabulary (mail/repository.py::_normalize_mail_status) --
// NOT the internal send-pipeline states (queued/sending/replied/...), which the API
// never exposes under this field.
export type SupplierMailStatus = 'not_sent' | 'sent' | 'waiting' | 'answered' | 'error' | 'delivery_unknown';

export interface RequestSupplierRow {
  id: number;
  external_key: string;
  name: string;
  email: string;
  host: string;
  inn: string;
  kind: string;
  region: string;
  role: string;
  phone: string;
  mail_status: SupplierMailStatus;
  last_error: string | null;
  unread_count: number;
  found_url: string | null;
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
  email_count: number;
  site_count: number;
  /** Set only once this supplier is confirmed/linked into the global
   * картотека -- null means there's no company card to open yet. */
  global_supplier_id: number | null;
}

export interface RequestDetail {
  request: RequestListItem;
  positions: RequestPosition[];
  items: RequestSupplierRow[];
}

// Bulk-compose ("Написать") -- real endpoints already used by the legacy
// frontend (frontend/src/lib/api.ts): /api/mail/deliverability/preflight and
// /api/mail/send-bulk. mail_account_id is optional everywhere; the backend
// picks the workspace's connected account when omitted.
export interface SupplierSendInput {
  id?: number;
  email: string;
  name?: string;
  host?: string;
  external_key?: string;
  inn?: string;
  global_supplier_id?: number | null;
}

export interface MailAttachment {
  filename: string;
  mime_type: string;
  size?: number;
  content_base64: string;
}

export interface MailTemplate {
  subject: string;
  body: string;
  attachments: MailAttachment[];
  updated_at: string | null;
}

export type PreflightStatus = 'PASS' | 'WARNING' | 'BLOCK';

export interface PreflightRecipientResult {
  email: string;
  status: 'eligible' | 'excluded';
  reasons: string[];
  domain?: string;
}

export interface PreflightResult {
  ok?: boolean;
  status: PreflightStatus;
  planned: number;
  eligible: number;
  excluded: number;
  unique_domains: number;
  recipient_results: PreflightRecipientResult[];
}

export interface QueuedBulkResult {
  job_id: number;
  message_id: number;
  thread_id: number;
  operation_id: number;
}

export type RelationshipStatus = 'none' | 'favorite' | 'blacklisted';

export interface GlobalSupplierRegistry {
  ogrn: string;
  status: string;
  is_active: boolean | null;
  registered_at: string;
}

export interface GlobalSupplierFinances {
  report_year: number | null;
  revenue: number | null;
  profit: number | null;
}

export interface GlobalSupplierSummary {
  id: number;
  inn: string;
  name: string;
  site: string;
  email: string | null;
  phone: string | null;
  note: string;
  categories: string[];
  total_requests: number;
  /** Whole percent already, 0..100 -- NOT a 0..1 ratio (confirmed against
   * mail/repository.py::_compose_global_supplier, which computes
   * round(answered/sent*100)). formatPercent() expects a 0..1 ratio, so
   * divide by 100 before passing this value to it. */
  response_rate: number;
  avg_response_hours: number | null;
  last_contact_at: string | null;
  relationship_status: RelationshipStatus;
  blacklist_reason: string | null;
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
}

export interface GlobalSupplierHistoryEntry {
  request_id: number;
  supplier_id: number;
  request_title: string;
  date: string;
  outcome: 'not_sent' | 'sent' | 'waiting' | 'answered' | 'error' | 'delivery_unknown';
  rating: number | null;
}

export interface GlobalSupplierIssue {
  reason: string;
  comment: string;
  correct_inn: string;
  source: string;
  reported_at: string;
}

export interface GlobalSupplierDetail extends GlobalSupplierSummary {
  history: GlobalSupplierHistoryEntry[];
  issues: GlobalSupplierIssue[];
}

export interface Task {
  id: number;
  title: string;
  due_date: string | null;
  done: boolean;
  request_id: number | null;
  supplier_id: number | null;
  inbox_message_id: number | null;
  created_at: string;
  completed_at: string | null;
  request_name: string | null;
  supplier_name: string | null;
}

export type MailDirection = 'outbound' | 'inbound';

export interface MailMessage {
  id: number;
  direction: MailDirection;
  from_email: string;
  to_email: string;
  subject: string;
  body_text: string | null;
  body_html: string | null;
  status: string;
  error: string | null;
  message_id: string | null;
  created_at: string;
  sent_at: string | null;
  has_remote_images?: boolean;
}

export interface ThreadSummary {
  id: number;
  request_id: number;
  supplier_id: number;
  /** suppliers.id above is request-scoped; this is the global картотека id
   * tasks/notes-that-need-it must use instead -- null until the supplier is
   * confirmed/linked. */
  global_supplier_id: number | null;
  subject: string;
  last_message_at: string | null;
  created_at: string;
  request_name: string;
  supplier_name: string;
  supplier_email: string;
  supplier_host: string;
  messages_count: number;
  replies_count: number;
  unread_count: number;
  pending_outbound_count: number;
  last_outbound_status: string | null;
  last_message_direction: MailDirection | null;
  is_important: boolean;
  priority: 1 | 2 | 3 | null;
}

/** Light row from /api/mail/inbox/preview — no body text, matches the real endpoint. */
export interface InboxPreview {
  id: number;
  from_email: string;
  subject: string;
  received_at: string;
  unread: boolean;
}

/** Full body, fetched separately via /api/mail/inbox/conversation when a preview row is opened. */
export interface InboxConversation {
  id: number;
  from_email: string;
  to_email: string;
  subject: string;
  body_text: string | null;
  body_html: string | null;
  received_at: string;
  replies: MailMessage[];
}

/** Link candidate, fetched separately via /api/mail/inbox/{id}/suggestions. */
export interface InboxSuggestion {
  request_id: number;
  supplier_id: number;
  request_name: string;
  supplier_name: string;
  supplier_email: string;
  match: 'exact' | 'domain';
}

export interface ManualLinkRequestOption {
  id: number;
  name: string;
  description: string | null;
  sender_name: string;
  company_name: string;
  status: string;
  supplier_names: string[];
  supplier_emails: string[];
}

export interface DashboardSummary {
  kpis: {
    active_requests: number;
    searching_requests: number;
    new_replies: number;
    attention: number;
    unmatched_mail: number;
  };
  requests: RequestListItem[];
}

export type LogisticsQuoteStatus = 'success' | 'unavailable' | 'invalid_input' | 'rate_limited' | 'provider_error';

export interface LogisticsQuote {
  id: number;
  request_id: number;
  supplier_id: number | null;
  carrier: string;
  route_from: string;
  route_to: string;
  cargo_places: number;
  cargo_weight_kg: number;
  cargo_volume_m3: number;
  cargo_max_dims_cm: string;
  price: number | null;
  currency: string;
  term_days: number | null;
  cost_breakdown: Record<string, number | null>;
  status: LogisticsQuoteStatus;
  calculated_at: string;
}

export interface LogisticsQuoteCargoInput {
  places: number;
  weight_kg: number;
  volume_m3: number;
  max_length_cm: number;
  max_width_cm: number;
  max_height_cm: number;
}

export interface MessageSearchResult {
  message_id: number;
  thread_id: number;
  request_id: number;
  supplier_id: number;
  direction: MailDirection;
  subject: string;
  body_text: string;
  created_at: string;
  request_name: string;
  supplier_name: string;
}

export interface AuthUser {
  email: string;
  display_name: string;
  workspace_name: string;
}
