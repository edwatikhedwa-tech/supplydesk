import type { ThreadSummary } from './types';

// The real backend has no `response_status` field on ThreadSummary (verified
// against a live LOCAL_CANONICAL instance on 2026-09-08) — it is derived
// client-side from signals the API does provide.
export type ResponseStatus = 'none' | 'waiting' | 'answered';

export function threadResponseStatus(thread: ThreadSummary): ResponseStatus {
  if (thread.replies_count > 0) return 'answered';
  if (thread.messages_count > 0) return 'waiting';
  return 'none';
}

// The real MailMessage has no `from_name` — the display name is derived from
// which side of the thread sent the message.
export function messageSenderName(direction: 'inbound' | 'outbound', supplierName: string, ownerDisplayName: string): string {
  return direction === 'inbound' ? supplierName : ownerDisplayName;
}
