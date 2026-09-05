// Data contracts for the v2 prototype, trimmed from the real SupplyDesk
// backend/frontend contract (frontend/src/lib/types.ts) to the fields this
// slice actually renders. Field names and semantics are kept identical to
// the real contract so this shell can be wired to the live API later
// without a reshape.

export type RequestStatus = 'draft' | 'searching' | 'updating' | 'completed' | 'error';

export interface RequestListItem {
  id: number;
  name: string;
  description: string | null;
  deadline: string | null;
  sender_name: string;
  company_name: string;
  created_at: string;
  updated_at: string | null;
  status: RequestStatus;
  search_progress: number;
  search_total: number;
  positions_count: number;
  suppliers_count: number;
  sent_count: number;
  replies_count: number;
  unread_count: number;
}

export type RelationshipStatus = 'none' | 'favorite' | 'blacklisted';

export interface GlobalSupplierSummary {
  id: number;
  inn: string;
  name: string;
  site: string;
  email: string | null;
  phone: string | null;
  categories: string[];
  total_requests: number;
  response_rate: number; // 0..1
  avg_response_hours: number | null;
  last_contact_at: string | null;
  relationship_status: RelationshipStatus;
  blacklist_reason: string | null;
}

export type MailDirection = 'outbound' | 'inbound';

export interface MailMessage {
  id: number;
  direction: MailDirection;
  from_email: string;
  from_name: string;
  to_email: string;
  subject: string;
  body_text: string;
  created_at: string;
  status: 'accepted' | 'queued' | 'failed' | 'delivered' | 'read';
  attachments?: { filename: string; size_kb: number }[];
}

export interface ThreadSummary {
  id: number;
  request_id: number;
  supplier_id: number;
  request_name: string;
  supplier_name: string;
  supplier_email: string;
  supplier_host: string;
  last_message_at: string;
  messages_count: number;
  unread_count: number;
  last_message_direction: MailDirection;
  response_status: 'none' | 'waiting' | 'answered';
}

export interface RequestGroup {
  request_id: number;
  request_name: string;
  deadline: string | null;
  threads: ThreadSummary[];
}

export interface UnmatchedMail {
  id: number;
  from_email: string;
  subject: string;
  preview: string;
  received_at: string;
  unread: boolean;
  suggestion: { request_id: number; request_name: string; supplier_name: string; match: 'exact' | 'domain' } | null;
}

export interface DashboardSummary {
  kpis: {
    active_requests: number;
    searching_requests: number;
    new_replies: number;
    attention: number;
    unmatched_mail: number;
  };
}
