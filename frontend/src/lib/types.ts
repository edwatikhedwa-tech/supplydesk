export type SupplierMailStatus = 'not_sent' | 'sent' | 'waiting' | 'answered' | 'error' | 'delivery_unknown';
export type SupplierDeliveryStatus = 'not_sent' | 'queued' | 'accepted' | 'failed' | 'delivery_unknown' | 'bounced' | 'cancelled' | 'mixed';
export type SupplierResponseStatus = 'none' | 'waiting' | 'answered';

export interface SupplierDeliveryCounts {
  not_sent: number;
  queued: number;
  accepted: number;
  failed: number;
  delivery_unknown: number;
  bounced: number;
  cancelled: number;
}

export interface SupplierContact {
  supplier_id: number;
  email: string;
  host: string;
  mail_status: SupplierMailStatus;
  delivery_status?: SupplierDeliveryStatus;
  response_status?: SupplierResponseStatus;
  last_error?: string | null;
}

export interface SupplierSendInput {
  id?: number;
  email: string;
  name?: string;
  host?: string;
  external_key?: string;
  inn?: string;
  global_supplier_id?: number | null;
}

export interface Supplier {
  id: number;
  external_key: string;
  name: string;
  email: string | null;
  host: string;
  inn: string;
  /** ИНН, введённый человеком, не должен выглядеть как автоматически найденный. */
  inn_source?: 'manual' | 'auto' | '' | null;
  kind: string;
  region: string;
  role: string;
  phone: string;
  reason: string;
  source: string;
  /** Страница выдачи, по которой поставщик нашёлся — чтобы «Почему найден»
   *  можно было проверить, а не только прочитать. Пусто у записей, созданных
   *  до появления таблицы search_result_sources. */
  found_url: string | null;
  covers: string[];
  position_keys: string[];
  site_unavailable: number;
  mail_status: SupplierMailStatus;
  /** Effective transport outcome aggregated across the company's email contacts. */
  delivery_status?: SupplierDeliveryStatus;
  /** Response axis is independent from SMTP transport. */
  response_status?: SupplierResponseStatus;
  delivery_counts?: SupplierDeliveryCounts;
  /** Сохраняет факт неопределённой отправки; закрытие вопроса не превращает её в sent. */
  delivery_issue_resolved?: boolean;
  last_error?: string | null;
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
  /** Ссылка на карточку компании в общей картотеке (`/suppliers?open=`).
   *  Пусто, если сайт ещё не связан с записью реестра. */
  global_supplier_id: number | null;
  /** Факторы риска из ЕГРЮЛ/ЕГРИП, ровно как их считает Checko (см.
   *  checko_client.py). `null` — не проверялись; `[]` — проверены, риска нет.
   *  В таблицах не показываются — данные оказались слишком шумными
   *  («массовый адрес» у половины арендаторов бизнес-центра). */
  risks: string[] | null;
  /** Непрочитанные ответы поставщика по этой заявке. Отличает «ответ пришёл»
   *  от «ответ уже прочитан» — у них разный цвет в таблице. */
  unread_count: number;
  /** Контакты и сайты компании, собранные из host-based строк одной заявки. */
  contacts?: SupplierContact[];
  contact_emails?: string[];
  contact_sites?: string[];
  site_count?: number;
  email_count?: number;
  /** Число email, для которых в этой заявке ещё не было отправки. */
  unsent_contact_count?: number;
  related_supplier_ids?: number[];
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
  search_depth: number;
  last_error: string | null;
  updated_at: string | null;
  positions_count: number;
  suppliers_count: number;
  sent_count: number;
  replies_count: number;
  mail_metrics?: RequestMailMetrics;
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
  mail_metrics?: RequestMailMetrics;
}

export interface RequestMailMetrics {
  outbound_total: number;
  queued: number;
  /** Historical count of SMTP-accepted messages; it may include later bounces. */
  accepted: number;
  accepted_effective: number;
  failed: number;
  delivery_unknown: number;
  bounced: number;
  cancelled: number;
  replies: number;
}

export interface DashboardSummary {
  kpis: {
    active_requests: number;
    searching_requests: number;
    new_replies: number;
    attention: number;
    /** Письма, которые система не смогла отнести к заявке — их
     *  привязывает человек (вкладка «Без привязки»). */
    unmatched_mail: number;
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
  /** Непрочитанные ответы поставщика. Гаснет при открытии треда — в отличие
   *  от replies_count, который считает все ответы за всё время. */
  unread_count: number;
  /** ID исходного inbox-письма для ручной связи без поставщика/треда. */
  manual_inbox_id?: number | null;
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
  delivery_resolved?: boolean;
  delivery_resolution?: { resolved_at: string; comment: string | null } | null;
  /** Внешние изображения в HTML письма заблокированы до явного показа. */
  has_remote_images?: boolean;
}

export interface MailTemplateAttachment {
  filename: string;
  mime_type: string;
  size: number;
  content_base64: string;
}

export interface MailTemplate {
  subject: string;
  body: string;
  attachments: MailTemplateAttachment[];
  updated_at: string | null;
}

export interface MailAccount {
  id: number;
  provider: string;
  provider_type?: string;
  email: string;
  email_address?: string;
  display_name?: string;
  auth_mode: 'oauth' | 'app_password' | string;
  credential_reference?: string | null;
  status: string;
  connected: boolean;
  outgoing_enabled: boolean;
  outgoing_health?: 'ready' | 'disabled' | 'error' | string;
  incoming_enabled: boolean;
  incoming_health?: 'healthy' | 'error' | 'pending' | 'disabled' | string;
  incoming_last_success_at?: string | null;
  incoming_last_error_at?: string | null;
  incoming_last_error?: string | null;
  token_expires_at?: string | null;
  last_error?: string | null;
  updated_at?: string | null;
}

export type CampaignStatus = 'active' | 'paused_for_review' | 'paused_for_health' | 'stopped' | 'completed';
export type PreflightStatus = 'PASS' | 'WARNING' | 'BLOCK';
export type ExclusionReason =
  | 'duplicate'
  | 'invalid_email'
  | 'suppressed'
  | 'hard_bounce'
  | 'unresolved_safety_state'
  | 'missing_email'
  | 'attachment_limit'
  | 'render_error'
  | string;

export interface PreflightRecipientResult {
  email: string;
  requested_email?: string;
  supplier_id?: number | null;
  selected_supplier_id?: number | null;
  contact_state?: string | null;
  alternate_selected?: boolean;
  domain?: string;
  status: 'eligible' | 'excluded';
  reasons: ExclusionReason[];
  personalization_level: number;
}

export interface PreviewTarget {
  normalized_email: string;
  supplier_id: number | null;
  to_email: string;
  subject: string;
  body_text: string;
  body_html: string;
  message_id_header: string;
  resend_of_message_id?: number | null;
  personalization_level: number;
}

export interface RolloutConfig {
  stage_1: number;
  stage_2: number;
  stage_3: number;
  manual_stage_approval: boolean;
}

export interface PreviewContract {
  frozen: boolean;
  renderer: string;
  snapshot_frozen_on: string;
  rerun_if_source_data_changed: boolean;
}

export interface EstimatedDuration {
  minimum: number;
  average: number;
  maximum: number;
}

export interface CampaignLimits {
  max_recipients: number;
}

export interface AccountBudget {
  max_per_hour: number;
  max_per_day: number;
}

export interface PacingMetadata {
  min_interval_seconds: number;
  max_interval_seconds: number;
}

export interface PreflightResult {
  ok?: boolean;
  dry_run?: boolean;
  preview?: boolean;
  preview_contract?: PreviewContract;
  status: PreflightStatus;
  planned: number;
  eligible: number;
  excluded: number;
  unique_domains: number;
  recipient_results: PreflightRecipientResult[];
  contact_selection?: {
    selected_companies: number;
    would_create: number;
    alternate_selected: number;
    already_contacted: number;
    answered: number;
    no_eligible_email: number;
    errors: number;
    ambiguous: number;
  };
  warnings: string[];
  blocks: string[];
  personalization_distribution: Record<string, number>;
  similarity_ratio: number;
  attachment_total_bytes: number;
  provider: string | null;
  provider_warning: string | null;
  campaign_limits: CampaignLimits;
  account_budget: AccountBudget;
  pacing: PacingMetadata;
  budget_warning: string | null;
  estimated_duration_seconds: EstimatedDuration;
  rollout: RolloutConfig;
  previews?: PreviewTarget[];
  error?: string;
  attachment_error?: string;
}

export interface CampaignHealth {
  permanent_failure_rate: number;
  transient_failure_rate: number;
  unknown_rate: number;
  provider_rejection_rate: number;
  hard_bounces: number;
}

export interface CampaignExcludedTarget {
  email: string;
  supplier_id: number | null;
  supplier_name?: string | null;
  reason: string;
}

export interface CampaignSummary {
  campaign_id: number;
  operation_id: number;
  request_id: number;
  mail_account_id: number;
  provider: string;
  status: CampaignStatus | string;
  stage: number;
  stage_limit: number;
  manual_stage_approval: boolean;
  planned: number;
  eligible: number;
  excluded: number;
  queued: number;
  waiting: number;
  attempted: number;
  accepted: number;
  accepted_in_campaign?: number;
  accepted_reconciled?: number;
  accepted_by_provider?: Record<string, number>;
  failed_permanent: number;
  failed_transient: number;
  historical_disputed_transient?: number;
  delivery_unknown: number;
  suppressed: number;
  cancelled: number;
  remaining: number;
  queued_provider_neutral?: number;
  provider_rejection_count: number;
  health: CampaignHealth;
  pause_reason: string | null;
  provider_warning: string | null;
  updated_at: string;
  excluded_targets?: CampaignExcludedTarget[];
}

export interface CampaignContinuationTarget {
  target_id: number;
  operation_target_id: number | null;
  ordinal: number;
  normalized_email: string;
  supplier_id: number | null;
  job_id: number | null;
  source_message_id: number | null;
  personalization_level: number;
}

export interface CampaignContinuationDryRun {
  dry_run: true;
  campaign_id: number;
  campaign_provider: string;
  campaign_status: string;
  current_mail_account_id: number;
  target_mail_account_id: number;
  target_provider: string;
  target_account_status: string;
  target_email: string;
  eligible_untouched: number;
  would_create: number;
  would_send_now: number;
  accepted_not_repeated: number;
  accepted_reconciled_not_repeated?: number;
  failed_not_repeated: number;
  historical_disputed_transient_not_repeated?: number;
  delivery_unknown_not_repeated: number;
  queued_in_current_campaign: number;
  cancelled_not_repeated: number;
  excluded_not_repeated: number;
  limit: number | null;
  selected_targets: CampaignContinuationTarget[];
  source_state: {
    schema: number;
    request_id: number;
    campaign_updated_at: string;
    campaign_status: string;
    campaign_provider: string;
    current_mail_account_id: number;
    target_mail_account_id: number;
    selected_target_ids: number[];
  };
  selection_fingerprint: string;
  safe: boolean;
  no_live_send: true;
  target_account?: MailAccount;
}

export interface CampaignContinuationApplyResult {
  ok: true;
  plan_id: number;
  operation_id: number;
  campaign_id: number;
  provider: 'mailru' | string;
  mail_account_id: number;
  limit: number;
  selected_count: number;
  created_count: number;
  skipped_count: number;
  jobs: Array<CampaignContinuationTarget & {
    job_id: number;
    message_id: number;
    thread_id: number;
  }>;
  skipped_targets: Array<CampaignContinuationTarget & { reasons: string[] }>;
  selection_fingerprint: string;
  no_live_send: true;
  smtp_data_calls: 0;
  idempotent_replay?: boolean;
  target_account?: MailAccount;
}

export interface CrossProviderRetryPreview {
  eligible: boolean;
  blocked_reasons: string[];
  request_id: number;
  supplier_id: number | null;
  recipient_masked: string;
  source: {
    job_id: number;
    message_id: number;
    attempt_id: number | null;
    provider: string | null;
    account_id: number | null;
    account_email?: string | null;
    rfc_message_id?: string | null;
    recipient_masked: string;
    supplier_id: number | null;
    job_status: string | null;
    message_status: string | null;
    outcome: string | null;
    provider_classification: string | null;
    irreversible_reached: boolean;
    smtp_evidence: {
      smtp_stage: string | null;
      smtp_code: number | null;
      smtp_enhanced_status: string | null;
      provider_response_safe: string | null;
      exception_class: string | null;
    } | null;
  };
  target_account: MailAccount;
  retry_reason: 'proven_provider_rejection' | string;
  selection_fingerprint: string;
  would_create: number;
  would_send_now: 0;
  requires_operator_confirmation: true;
  no_live_send: true;
  smtp_data_calls: 0;
}

export interface CrossProviderRetryApplyResult {
  ok: true;
  retry_plan_id: number;
  operation_id: number;
  request_id: number;
  supplier_id: number;
  original_job_id: number;
  original_message_id: number;
  original_attempt_id: number;
  provider: 'mailru' | string;
  target_mail_account_id: number;
  recipient_masked: string;
  retry_reason: 'proven_provider_rejection' | string;
  status: string;
  job_id: number;
  message_id: number;
  message_id_header: string;
  selection_fingerprint: string;
  no_live_send: true;
  smtp_data_calls: 0;
  campaign_changed: false;
  idempotent_replay?: boolean;
  target_account?: MailAccount;
}

export interface QueuedBulkResult {
  job_id: number;
  message_id: number;
  thread_id: number;
  operation_id: number;
  campaign_id?: number | null;
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
  /** Внешние изображения в HTML письма заблокированы до явного показа. */
  has_remote_images?: boolean;
}

export interface InboxReply {
  id: number;
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
  has_remote_images?: boolean;
}

/** Полное непривязанное письмо для чтения в дашборде или во входящих. */
export interface InboxConversation extends InboxMessage {
  message_id?: string | null;
  references_header?: string | null;
  mail_account_id?: number;
  replies: InboxReply[];
}

/** Кандидат на привязку неразобранного письма: заявка + поставщик, чей адрес
 *  совпал с отправителем (`exact`) или живёт на том же домене (`domain`). */
/** Лёгкая карточка непривязанного письма — только для превью на дашборде,
 *  без тела письма (см. list_unmatched_incoming_preview). */
export interface InboxPreview {
  id: number;
  from_email: string;
  subject: string;
  received_at: string;
}

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
  risks: string[] | null;
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

export interface FinanceYear {
  report_year: number;
  revenue: number | null;
  profit: number | null;
}

export interface GlobalSupplierDetail extends GlobalSupplierSummary {
  history: GlobalSupplierHistoryEntry[];
  issues: GlobalSupplierIssue[];
  registry: GlobalSupplierRegistry | null;
  finances: GlobalSupplierFinances | null;
  /** Динамика выручки и прибыли, по возрастанию года (до 6 последних). */
  finance_history: FinanceYear[];
}
