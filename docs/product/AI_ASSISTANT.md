---
document_id: DOC-PRODUCT-AI-ASSISTANT-001
status: CURRENT
canonical: true
owner: audit
updated_at: 2026-09-17
source_commit: dc66b0b
---

# AI Assistant

## CURRENT (verified in code, 2026-09-17)

**Real feature, not a mock.** Calls RouterAI (`https://routerai.ru/api/v1`, OpenAI-SDK-compatible)
via `backend/integrations/llm/routerai_client.py`. `ROUTERAI_CHAT_KEY` env var; if unset,
`send_message` returns a real "not configured" status rather than a fake answer.

**Route:** `POST /api/ai/chat` → `backend/domain/ai_agent/chat_service.py::AiChatService`.

**Context assembly** (`chat_service._build_context`):
- Frontend sends `thread_ids` (the active thread plus any user-picked extras).
- Extras are UX-filtered client-side to threads with `threadResponseStatus === 'answered'` —
  but this is presentation only.
- **The real security/correctness boundary is server-side**: every thread id is re-validated via
  `get_thread_owned(workspace_id, request_id, thread_id)`, which silently drops anything that
  doesn't actually belong to this workspace+request. A forged or stale thread id cannot smuggle
  another workspace's data in.
- Per surviving thread: supplier name/email + up to 10 most-recent *communication* messages
  (inbound, or outbound past a transport marker — failed pre-send attempts excluded), each
  trimmed to 4500 chars (head+tail kept). Whole context hard-capped at 40,000 chars.
- Daily spend cap (`ai_chat_usage`, default 10₽/workspace/user/day) checked **before** calling
  the model; over the cap returns `status="limit_reached"` without spending a token.

## The historical "all suppliers leak into context" bug — VERIFIED FIXED

The exact concern named in the audit brief ("раньше в AI могли попадать все поставщики заявки
вместо поставщиков, с которыми была коммуникация") is a real, documented, already-fixed bug —
**not a currently-active one**:

- Commit `0d16945` (2026-09-10): *"siblingThreads and the per-thread 'add to AI context'
  checkbox now require `messages_count > 0` — a supplier merely matched/found for a request,
  never actually emailed, must never appear as an AI-context source."*
- Current frontend filter is stricter still: only *replied* threads (`'answered'`) are offered as
  extra context, not merely emailed ones.
- Backend enforcement doesn't depend on the frontend at all: a `mail_threads` row only exists
  once real communication occurred (`list_threads`'s `_communication_message_predicate`), so a
  supplier merely linked to a request but never emailed has no thread to leak in the first place.

**CURRENT = EXPECTED here.** No gap to record for this specific concern.

## Gaps found (not the one asked about, but real)

- `GAP-013` (P3): the 40,000-char context budget is a blunt suffix cut of the whole assembled
  string — could drop the most-recently-added supplier's messages rather than budgeting per
  supplier. The inbox-conversation-mode path (single unmatched-mail thread, not request-scoped)
  has no message-count cap at all, only per-message char trimming.
- No per-minute/burst rate limit — only the cumulative daily ruble cap. A user could still burst
  many calls quickly until the cap trips.
- Character-based, not token-based, budgeting — a token-dense script (non-Latin text, code,
  tables) could produce a larger real token count than the char budget assumes.

## Product invariant

`INV-AI-001` (see [`../spec/PRODUCT_INVARIANTS.md`](../spec/PRODUCT_INVARIANTS.md)): a supplier
must never enter AI context solely because it is linked to a request — only because real
communication (a `mail_threads` row backed by an actual message) exists. **Status: HELD**,
verified by both the frontend filter and the server-side `get_thread_owned` boundary.
