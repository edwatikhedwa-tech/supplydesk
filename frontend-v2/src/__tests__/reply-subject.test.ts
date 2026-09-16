import { describe, it, expect } from 'vitest';

/**
 * Regression tests for the subject-prefix fix: when the existing subject
 * already starts with "Re:" (case-insensitive), do NOT add a second one.
 * This mirrors the logic in Messages.tsx::sendReply.
 */
function buildReplySubject(firstSubject: string | null, activeThreadSubject: string): string {
  if (!firstSubject) return activeThreadSubject;
  if (/^re:\s*/i.test(firstSubject)) return firstSubject;
  return `Re: ${firstSubject}`;
}

describe('reply subject prefix (Re: dedup)', () => {
  it('adds Re: when subject is bare', () => {
    expect(buildReplySubject('Товарное предложение', '')).toBe('Re: Товарное предложение');
  });

  it('does NOT add duplicate Re: when already prefixed with Re:', () => {
    expect(buildReplySubject('Re: Товарное предложение', '')).toBe('Re: Товарное предложение');
  });

  it('does NOT add duplicate Re: for lowercase re:', () => {
    expect(buildReplySubject('re: товар', '')).toBe('re: товар');
  });

  it('does NOT add duplicate Re: for mixed-case RE:', () => {
    expect(buildReplySubject('RE: Товар', '')).toBe('RE: Товар');
  });

  it('falls back to thread subject when no messages', () => {
    expect(buildReplySubject(null, 'Тема треда')).toBe('Тема треда');
  });
});