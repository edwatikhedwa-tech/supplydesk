import { describe, it, expect } from 'vitest';
import { threadResponseStatus } from '@/lib/derive';
import type { ThreadSummary } from '@/lib/types';

describe('threadResponseStatus', () => {
  const base = (overrides: Partial<ThreadSummary> = {}): ThreadSummary => ({
    id: 1,
    request_id: 1,
    supplier_id: 1,
    global_supplier_id: null,
    subject: '',
    supplier_name: '',
    supplier_email: '',
    supplier_host: '',
    last_message_at: null,
    created_at: '',
    request_name: '',
    messages_count: 0,
    replies_count: 0,
    unread_count: 0,
    pending_outbound_count: 0,
    last_outbound_status: null,
    last_message_direction: null,
    is_important: false,
    priority: null,
    conversation_status: null,
    needs_followup: false,
    ...overrides,
  });

  it('returns answered when replies_count > 0', () => {
    expect(threadResponseStatus(base({ replies_count: 1 }))).toBe('answered');
    expect(threadResponseStatus(base({ replies_count: 5 }))).toBe('answered');
  });

  it('returns waiting when replies_count === 0 but messages_count > 0', () => {
    expect(threadResponseStatus(base({ messages_count: 1 }))).toBe('waiting');
    expect(threadResponseStatus(base({ messages_count: 3, replies_count: 0 }))).toBe('waiting');
  });

  it('returns none when both zero', () => {
    expect(threadResponseStatus(base({ messages_count: 0, replies_count: 0 }))).toBe('none');
  });
});