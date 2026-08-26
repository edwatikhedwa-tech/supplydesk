export type SupplierMailStatus = 'not_sent' | 'sent' | 'waiting' | 'answered' | 'error';

export interface Supplier {
  id: number;
  external_key: string;
  name: string;
  email: string | null;
  host: string;
  inn: string;
  kind: string;
  region: string;
  role: string;
  phone: string;
  reason: string;
  source: string;
  covers: string[];
  position_keys: string[];
  site_unavailable: number;
  mail_status: SupplierMailStatus;
  last_error?: string | null;
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
}

export type RequestStatus = 'draft' | 'searching' | 'updating' | 'completed' | 'error';

export interface RequestListItem {
  id: number;
  name: string;
  description: string | null;
  deadline: string;
  sender_name: string;
  company_name: string;
  created_at: string;
  status: RequestStatus;
  search_progress: number;
  search_total: number;
  last_error: string | null;
  updated_at: string | null;
  positions_count: number;
  suppliers_count: number;
  sent_count: number;
  replies_count: number;
}

export interface RequestPosition {
  id: number;
  request_id: number;
  position_key: string;
  name: string;
  quantity: string;
  created_at: string;
}

export interface RequestDetail {
  request: RequestListItem;
  positions: RequestPosition[];
  items: Supplier[];
}

export interface DashboardSummary {
  kpis: {
    active_requests: number;
    searching_requests: number;
    new_replies: number;
    attention: number;
  };
  requests: RequestListItem[];
}

export interface BlacklistEntry {
  id: number;
  external_key: string;
  company_name: string;
  level: string;
  reason: string;
  created_at: string;
  restored_at: string | null;
  host: string | null;
  email: string | null;
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
  supplier_external_key: string;
  messages_count: number;
  replies_count: number;
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
  in_reply_to: string | null;
  references_header: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface InboxMessage {
  id: number;
  from_email: string;
  to_email: string;
  subject: string;
  body_text: string | null;
  body_html: string | null;
  received_at: string;
  status: string;
  provider_message_id?: string | null;
}

export interface AuthUser {
  email: string;
  display_name: string;
  workspace_name: string;
}

export type RelationshipStatus = 'none' | 'favorite' | 'blacklisted';

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
  response_rate: number;
  avg_response_hours: number | null;
  last_contact_at: string | null;
  relationship_status: RelationshipStatus;
  avg_deal_rating: number | null;
  blacklist_reason: string | null;
  blacklisted_at: string | null;
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
}

export interface GlobalSupplierHistoryEntry {
  request_id: number;
  supplier_id: number;
  request_title: string;
  date: string;
  outcome: SupplierMailStatus;
  rating: number | null;
}

export interface GlobalSupplierIssue {
  reason: string;
  comment: string;
  correct_inn: string | null;
  source: 'manual' | 'auto';
  reported_at: string;
}

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

export interface GlobalSupplierDetail extends GlobalSupplierSummary {
  history: GlobalSupplierHistoryEntry[];
  issues: GlobalSupplierIssue[];
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
}
