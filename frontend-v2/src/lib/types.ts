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
  response_rate: number; // 0..1
  avg_response_hours: number | null;
  last_contact_at: string | null;
  relationship_status: RelationshipStatus;
  blacklist_reason: string | null;
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
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
