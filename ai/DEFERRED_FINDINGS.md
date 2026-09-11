---
document_id: DEFERRED-FINDINGS-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-11
source_commit: c076e1be385c3ae6da2716159e1f46fc2fce23d7
---

# Deferred Findings

Only unresolved, accepted-risk, or explicitly superseded findings belong in
this current register. Resolved findings and full chronology are preserved in
[`ai/history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md`](history/2026/09/DEFERRED_FINDINGS-CHRONICLE-20260901.md).

## FINDING-035 — No coordination signal between concurrent sessions editing the same branch

- ID: `FINDING-035`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: During `TASK-MESSAGES-QUOTE-CHECKO-DESIGN-SEND-20260911`, the
  working tree repeatedly picked up unrelated changes from another
  concurrent session/agent on the same branch (`Frame.tsx`, logistics/
  Dellin client changes, a differently-styled `ConversationStatusSelect`)
  between tool calls, with no in-session signal that this had happened
  other than the file-changed-on-disk system reminder. `ai/ACTIVE_TASK.md`
  exists for exactly this coordination purpose but was not consistently
  read/updated by whichever session made those changes.
- Impact: Low probability but real risk of two sessions silently
  overwriting each other's in-progress edits to the same file, or shipping
  a combined commit neither session fully reviewed alone.
- Why deferred: A process/discipline gap, not a code defect — no safe
  automated fix; needs an owner decision on workflow (e.g. always check
  `ai/ACTIVE_TASK.md` before a long edit session, or avoid running
  multiple sessions against the same branch concurrently).
- Next step: owner decides whether concurrent same-branch sessions are an
  accepted working style; if so, tighten `ai/ACTIVE_TASK.md` usage
  discipline (a session claims a task there before editing, clears it when
  done).

## FINDING-034 — No E2E/visual-regression coverage for frontend-v2

- ID: `FINDING-034`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: All UI verification this session (status-select redesign,
  scroll-preservation fix, default-filter change, quote folding) was done
  by hand through the Browser tool — screenshots, computed-style checks,
  manual click sequences. No Playwright/axe/Storybook setup exists for
  `frontend-v2` (confirmed absent; see also the project's own
  `frontend-v2-migration-reviewer` agent description, which names this gap
  explicitly).
- Impact: Manual verification is slow, easy to skip under time pressure,
  and does not run automatically on future changes — a regression in, say,
  the status-filter default or the scroll-preservation fix would only be
  caught by another manual pass.
- Why deferred: Standing up even a minimal Playwright harness is
  substantial, cross-cutting work, not a fix for a single defect — needs
  its own scoped task.
- Next step: a follow-up task adds a minimal Playwright smoke suite for
  `frontend-v2` (open Messages, select a thread, change a status, verify
  the filter default and one real send-path in a disposable-DB fixture)
  as a first slice, not full coverage at once.

## FINDING-033 — Backend test suite carries a permanently-accepted 2-failure/9-error baseline

- ID: `FINDING-033`
- Severity: `LOW`
- Status: `RESOLVED — genuine 0 failures / 0 errors baseline now, both root
  causes fixed rather than the marker text guessed at`
- Evidence: `python scripts/run_test_suite.py` has returned the same
  `failures=2, errors=9` baseline across every run this session (and per
  `ai/CURRENT_STATE.md`, across prior sessions too) — the two `POLICY-022`/
  `POLICY-026` governance-marker failures on `AGENTS.md`/`CLAUDE.md`, and
  errors from the `SESSION_WORKSPACE_HARD_GATE` workspace-guard test
  expecting a marker that `CLAUDE.md` does not currently contain (see
  `tests/diagnostics/test_workspace_guard.py`). Every session, including
  this one, treats this as "the known baseline" rather than something to
  fix.
- Impact: A baseline that never gets to zero is a real long-term risk —
  new genuine failures could land inside this same count and go unnoticed
  because "N failures" already reads as normal. Also directly costs signal
  value: `scripts/run_test_suite.py`'s output cannot be trusted at a glance
  to mean "something broke" vs "same as always."
- Why deferred: Fixing the two governance-marker failures means editing
  `AGENTS.md`/`CLAUDE.md`'s own policy text to satisfy
  `test_adapters_point_to_the_single_canonical_gate` and the `POLICY-022`/
  `POLICY-026` checks — a policy-document change, not an application fix,
  and out of scope for the tasks that ran into it this session.
- Resolution, the 2 failures: read `ai/tools/validate_vibecoding.py`'s exact
  checks instead of guessing at wording. `POLICY-026` needed the literal
  substring `"new session"` in both files (both said "a new Claude Code
  session"/"a new Codex session" — broken up by the product name, so never
  matched) and `"action-specific check"` in `AGENTS.md` specifically
  (worded differently there than in `CLAUDE.md`, which already had it).
  `POLICY-022` needed the literal substrings `"exactly once in the final
  response"` and `"never emit it in intermediate"` in both files — neither
  file stated the VibeCoding acknowledgement's final-only semantics at all
  (`ai/VIBECODING_RULES.md`, the canonical source, already did; the
  per-agent entrypoints didn't restate it). `test_adapters_point_to_the_
  single_canonical_gate` needed both files to name the canonical
  `SESSION_WORKSPACE_HARD_GATE` (`ai/AI_CONTRACT.md` §13) by name in their
  own workspace-guard sections, tying the local guard description to the
  one canonical concept instead of describing it as if invented locally.
  First attempt at the ACK-semantics sentence introduced the exact
  substrings but line-wrapped the markdown so `"never emit it in\nintermediate"`
  had a literal newline inside the required phrase — `read_text()` does no
  whitespace normalization, so the substring check still failed; caught by
  re-running the validator immediately after the edit rather than assuming
  it worked, fixed by keeping the phrase on one line.
- Resolution, the 9 errors: all nine were the same root cause —
  `tests/diagnostics/test_change_classifier.py` hardcoded `"pwsh"`
  (PowerShell Core) as the interpreter for `scripts/ci/classify_changes.ps1`,
  but this machine only has Windows PowerShell 5.1 (`powershell.exe`) —
  confirmed via `where pwsh` (not found) and `where powershell` (found).
  Before treating this as unfixable environment drift, ran
  `classify_changes.ps1` directly under `powershell.exe`: it worked
  correctly and produced the exact expected classification output, proving
  the script itself uses no PS7-only syntax and the mismatch was purely in
  which executable name the test hardcoded. Fixed by resolving the
  interpreter once via `shutil.which("pwsh") or shutil.which("powershell")`
  instead of a hardcoded name — real CI (which has `pwsh`) is unaffected,
  local Windows dev machines with only Windows PowerShell now work too.
  This means these 9 tests had never actually exercised
  `classify_changes.ps1` on this machine, in any session, until now.
- Verification: `python scripts/run_test_suite.py` — `failures=0`,
  `errors=0` (down from the standing `2`/`9`), same `587` tests and `2`
  skipped as before the fix (nothing newly skipped or removed).
- Next step: none for this finding. If a future local run ever needs
  `pwsh` specifically (not just PowerShell-compatible syntax), that's a
  separate, real environment gap to raise then — not implied by this fix.

## FINDING-032 — No systematic audit for other raw-exception-message secret leaks

- ID: `FINDING-032`
- Severity: `MEDIUM`
- Status: `RESOLVED — audited every real provider client; extracted the
  redaction into a shared helper; XMLRiver had the same vulnerable
  pattern, now fixed; Dellin/RouterAI/DaData confirmed not exposed`
- Evidence: This session found and fixed one real secret leak
  (`backend/integrations/registry/checko_client.py`: `requests.HTTPError`'s
  own `__str__` embeds the full request URL, `key=<real Checko key>`
  included, and that string reached the browser verbatim in
  `/api/requests/{id}/suppliers/{id}/inn`'s JSON response — confirmed via a
  real network-response inspection before and after the fix). The fix
  (`_redact_key`) was scoped to exactly that one call site. No systematic
  check was made for the same pattern elsewhere (any other provider client
  that builds an error string from a caught exception whose `__str__`
  might embed a URL with credentials/tokens in it — e.g. `dellin_client.py`,
  the Yandex/Mail.ru OAuth token-refresh paths, RouterAI's client).
- Impact: An unaudited codebase could have other, still-live instances of
  the exact same defect class this session already proved is real and
  reaches the browser.
- Why deferred: A full audit of every provider client's error-message
  construction is a distinct, scoped task, not a natural extension of the
  Checko-specific fix that found this pattern.
- Resolution: Grepped every `backend/integrations/` client and `mail/
  providers/` for `f"...{exc}"`/`str(exc)` patterns, then checked each
  candidate's actual auth mechanism (URL query param vs. header vs. request
  body — only the first can leak through a `requests` exception's `__str__`,
  which embeds the request URL but never headers or body). Findings:
  `xmlriver_client.py` had the exact same vulnerable pattern as Checko
  (`?key=...` query auth) in its connection-error retry path — fixed.
  `dellin_client.py` (key in the JSON body, never the URL),
  `routerai_client.py` (`Authorization: Bearer` header), and
  `dadata_client.py` (`Authorization: Token` header) are not exposed to
  this defect class — confirmed by reading their actual request
  construction, not assumed from naming. `mail/providers/` (Yandex/Mail.ru)
  has no `f"...{exc}"`/`str(exc)` pattern at all. The redaction itself was
  extracted from Checko's local `_redact_key` into a shared
  `backend/integrations/secret_redaction.py::redact_url_credentials`
  (covers `key`/`token`/`api_key`/`apikey`/`appkey`/`secret`/
  `access_token`, case-insensitive), used by both `checko_client.py` and
  `xmlriver_client.py` now, so the next client with this pattern has a
  ready-made fix instead of reinventing it. Proven by
  `tests/test_secret_redaction.py` (6 tests): the shared helper in
  isolation, plus two tests that reproduce the live defect shape
  end-to-end — a real `requests.ConnectionError` raised inside a mocked
  `session.get`, embedding a real-looking key in the URL exactly as the
  live bug did, asserting the client's actual returned/raised error message
  contains `key=***` and never the real key — for both `CheckoClient` and
  `XmlRiverClient`. Full suite re-run clean at the existing baseline after
  the change.
- Next step: none for this finding. If a future provider client
  authenticates via a URL query parameter, route its error-message
  construction through `redact_url_credentials` from the start.

## FINDING-031 — All three configured `CHECKO_KEY` values are invalid (local environment)

- ID: `FINDING-031`
- Severity: `MEDIUM`
- Status: `OPEN — needs owner action`
- Evidence: Direct live test this session (`requests.get` against
  `https://api.checko.ru/v2/company` with each of `CHECKO_KEY`,
  `CHECKO_KEY_2`, `CHECKO_KEY_3` from the local `.env`) returned
  `401 {"meta": {"message": "API-ключ не действителен"}}` for all three,
  not just quota exhaustion. `CheckoClient`'s rotation only advances on a
  quota-exhaustion signature, not a flat invalid-key 401, so in the current
  state rotation would not have helped even if it triggered.
- Impact: Manual-ИНН lookup and enrichment retries always land on
  `checko_status: "unavailable"` locally — the UI degrades correctly (no
  crash, ИНН still saved), but no real Checko data has been loading
  locally for some unknown period before this session. Related to but
  distinct from `FINDING-024` (production has no `CHECKO_KEY` configured
  at all); this finding is that the ones that *are* configured, locally,
  don't work either.
- Why deferred: Renewing/replacing third-party API keys is an owner
  action, not something an agent should do unilaterally.
- Next step: owner checks the Checko account dashboard for these keys'
  actual status (expired, revoked, wrong account) and updates local `.env`
  (and, per `FINDING-024`, Vercel production) with working keys.

## FINDING-030 — Mail queue can silently accumulate a backlog while outgoing is disabled, then flush it all at once

- ID: `FINDING-030`
- Severity: `MEDIUM`
- Status: `RESOLVED — the outgoing-mail status endpoint now returns the
  live backlog, and Settings surfaces it both passively and in the
  enable-confirmation dialog`
- Evidence: While running the owner-authorized real send test this
  session, enabling the durable outgoing switch caused the queue worker to
  immediately drain not just the one new test job, but three other
  `mail_jobs` rows that had been sitting in `status='queued'` since
  `2026-09-10` (created during an earlier session's testing, `created_at`
  ~16-20 hours before they finally sent at `2026-09-11T12:15-12:17`). All
  four happened to be addressed to the same safe owner-controlled test
  address (`edwatikh@gmail.com`), so no real supplier was affected this
  time — confirmed by checking every `to_email` before and after. Nothing
  in the UI or API surfaced that a backlog existed before the switch was
  flipped.
- Impact: If a queued-but-unsent job had instead been addressed to a real
  supplier (e.g. a reply composed while outgoing was disabled, or queued
  during an outage), enabling the durable switch would send it
  immediately and silently, with no review step — the owner would have no
  chance to notice or cancel it first.
- Why deferred: Found as a side effect of an authorized send test, not the
  task's own subject; designing the right UX (visible backlog count?
  required review before flush? auto-expire stale queued jobs?) needs its
  own scoped decision, not a same-session guess.
- Resolution: `mail/repository.py::queued_send_backlog(workspace_id)` counts
  `mail_jobs` rows with `status='queued'` joined to their message's
  `created_at`, scoped to the caller's own workspace (verified with a
  second, different-workspace assertion in the same test — a workspace
  cannot see another workspace's backlog). `GET /api/mail/runtime/outgoing`
  now returns it alongside the two existing flags; `Settings.tsx` shows a
  passive warning next to the toggle ("В очереди N писем ждут отправки
  (самое старое — …)") whenever the count is non-zero, and repeats a
  sharper version inside the enable-confirmation dialog itself ("В очереди
  уже N писем — они уйдут немедленно вместе с новыми"), so the warning is
  visible both before and at the exact moment of the risky action.
  Extended the existing `test_eighty_four_queued_jobs_stay_queued_when_
  outgoing_is_off` test (already the real-data fixture for this exact
  scenario) with assertions that the backlog reports all 84, and that a
  different workspace ID sees zero. Verified live end-to-end in the
  browser beyond the unit test: queued one real test message (outgoing
  mail left off, so it genuinely never sent) via the real `/api/mail/send`
  endpoint, confirmed the Settings warning appeared with the correct count
  and "только что" age, confirmed the enable-confirmation dialog's text
  updated too, cancelled without enabling, then deleted the test job
  (which the DB confirmed was still `status='queued'`, i.e. never sent)
  and confirmed the warning disappeared again. Full suite re-run clean at
  the existing baseline after the change.
- Next step: none for this finding. Auto-expiring very old queued jobs
  (rather than just warning about them) is a separate, larger product
  decision the owner would need to make explicitly, not implied by this
  fix.

## FINDING-029 — No visible signal distinguishing local-dev vs. deployed-production runtime/database identity

- ID: `FINDING-029`
- Severity: `MEDIUM`
- Status: `RESOLVED — a runtime-identity badge now renders in Settings,
  sourced from the backend's own database-engine knowledge`
- Evidence: This session, the owner viewed the deployed production site
  (`supplydesk-2769.vercel.app`, real Postgres via `DATABASE_URL`) on their
  phone and saw outgoing mail "Включена," while being told (accurately, but
  without the scope being obvious) that outgoing had just been disabled —
  on a completely separate local SQLite-backed runtime
  (`127.0.0.1:8000`, `mail-data/supplier.sqlite3`) that the owner was not
  looking at. Nothing in the Settings UI (or anywhere else in the app)
  states which database/environment identity is currently being viewed.
- Impact: Confusion like this session's is easy to repeat, and the next
  time it could be about something with real consequences (e.g. someone
  believing a real-supplier send was blocked locally when the toggle that
  matters is the production one, or vice versa).
- Why deferred: Found while investigating the owner's own report of the
  above confusion; the right fix (what to show, where) is a small but
  real product decision, not a one-line patch to make mid-investigation.
- Resolution: `backend/http_auth.py::_auth_me` now returns a `runtime`
  object (`{environment, database}`) on every call, both authenticated and
  not, computed from `self.app.runtime.environment` and
  `bool(self.app.repository.database_url)` — the same signals the
  outgoing-mail gate itself already relies on, so the badge can never drift
  out of sync with the actual gate logic. The first attempt labeled the
  badge from `runtime.environment` directly ("Продакшн"/"Локальная
  разработка"), which turned out to be wrong: local dev is deliberately
  configured with `SUPPLYDESK_ENV=production` too (required for a real send
  test from a laptop), so `environment` alone cannot distinguish "this
  machine" from "the deployed site" — verified live (the badge read
  "Продакшн" against the local backend before the fix). Corrected to key
  the label off `database` instead (`sqlite` → "Эта машина (локально)",
  `postgres` → "Облако (Vercel)", `danger`-toned for the deployed case),
  which is the only signal that's actually always different between the
  two — confirmed live against the local backend post-fix (reads "Эта
  машина (локально)"). `frontend-v2/src/lib/AuthContext.tsx` exposes
  `runtime` via `useAuth()`; `Settings.tsx`'s `RuntimeBadge` renders it in
  the page header next to the outgoing-mail toggle it was specifically
  meant to disambiguate. `tsc -b`, lint, and the full backend suite
  (`scripts/run_test_suite.py`, 581 tests) all stayed clean/at-baseline
  after the change; `tests.test_mail_integrity`/`tests.test_outgoing_safety`
  (the modules covering `/api/auth/me` and the outgoing-mail gate this
  touches) re-run individually and pass.
- Next step: none for this finding. Whether to also surface it on the
  Login page (before a session exists) is a separate, smaller follow-up if
  the owner wants it.

## FINDING-028 — AI Stress Test 3 (history-aware reply): model re-asks already-answered questions

- ID: `FINDING-028`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: `TASK-MESSAGES-LINKS-STATUS-SEND-AI-20260910`'s owner-mandated
  Stress Test 3 (a real RouterAI call, `meta-llama/llama-3.3-70b-instruct`,
  disposable-DB fixture with a realistic 4-turn history: our question about
  chimney diameter → supplier answers and asks the diameter → we answer the
  diameter and ask about delivery time/whether install is included →
  supplier answers both). Asked: "Подготовь короткий ответ поставщику...
  Не задавай повторно вопросы, на которые поставщик уже ответил." The
  model's reply explicitly claimed it would not re-ask the diameter/install
  questions, then immediately asked whether the model is in stock and when
  it would be delivered — both already answered in the same history it had
  just been given ("В наличии сейчас нет, под заказ" / "Срок поставки — 3
  недели").
- Impact: A user relying on the "Подготовь ответ" feature to draft a reply
  could send a message that visibly ignores the supplier's own prior
  answer, which looks worse than not using AI assistance at all.
- Why deferred: Same 70B model already adopted this task per `DECISION-023`
  after Stress Test 1/2 evidence; a further model escalation or a
  structured (tool-calling / explicit fact-extraction-then-compose)
  prompting approach needs its own scoped evaluation, not a same-session
  re-guess.
- Next step: a follow-up task evaluates either a stronger model or a
  two-step prompt (extract already-answered facts as a structured list
  first, then compose the reply conditioned on that list) against the same
  reproducible disposable-DB fixture, so the fix has a red-to-green proof.

## FINDING-027 — AI Stress Test 2 (3-supplier comparison): price/term missed for a multi-option supplier message

- ID: `FINDING-027`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: Same task, Stress Test 2, real production-pattern data (request
  1059, 3 real suppliers: `СТРОЙ-КАМИН` states a price for one specific
  stove variant among several offered — "Стоимость — 285000 руб" — and a
  general "Срок изготовления... примерно 20 рабочих дней"; `ТАЛЬКОРУС`
  states a term but no numeric price; `УНИВЕРСАЛ` has no data yet, only
  asked a clarifying question back). Confirmed via direct inspection that
  both facts were present, untruncated, in the exact context string sent
  to the model (`AiChatService._build_context` output verified to contain
  both `"285000"` and `"20 рабочих"`). Both the 8B and the 70B model
  (before and after `DECISION-023`) reported `СТРОЙ-КАМИН`'s price and term
  as "не указано" despite the data being present — while correctly handling
  the other two suppliers (ТАЛЬКОРУС's stated term, no invented price;
  УНИВЕРСАЛ's genuine lack of any data). No cross-supplier fact bleed
  occurred in either run — that specific invariant held in both.
- Impact: A 3-way comparison can silently omit a real number for one
  supplier when that supplier's message describes multiple product options
  rather than one clean quote, without any hallucination — the omission
  itself is the defect, not a wrong value.
- Why deferred: Likely needs the same structured-extraction approach noted
  in `FINDING-028`, not a further blind model escalation; scoping that is
  a follow-up task, not a same-session re-guess.
- Next step: fold into the same follow-up task as `FINDING-028`.

## FINDING-026 — Live SMTP send verified from canonical production-mode runtime

- ID: `FINDING-026`
- Severity: `LOW`
- Status: `SUPERSEDED 2026-09-11 by verified live-mail evidence`
- Evidence: `TASK-MESSAGES-LINKS-STATUS-SEND-AI-20260910`'s live send/
  attachment acceptance (real UI, real composer, owner-authorized target:
  the owner's own connected mailbox) proved the entire pipeline end-to-end
  — real HTTP send request, real deliverability preflight, real
  `mail_messages`/`mail_attachments` rows with correct `In-Reply-To`/
  `References` chaining and correct attachment bytes — up to the point
  `mail/runtime.py`'s `RuntimeSession._base_outgoing_allowed()` requires
  `self.environment == "production"`. `SUPPLYDESK_ENV=development` in the
  local canonical `.env` (per `ai/CURRENT_STATE.md`'s `2026-09-03` entry,
  set deliberately: "this is real local development, not a deployment").
  Both `scripts/start_local_canonical.ps1 -AllowOutgoingMail` (env kill
  switch) and the owner-only `/api/mail/runtime/outgoing` durable DB flag
  were enabled for this test and reverted afterward; `effective_outgoing_enabled`
  stayed `false` throughout because of this third, environment-level gate.
- Resolution evidence: By explicit owner authorization, the canonical database
  identity and local runtime configuration were corrected to the current
  absolute database path and production mode. A single `MAIL_PROVIDER_CHECK`
  runtime acquired the live-mail lock; both connected accounts passed SMTP and
  IMAP authentication. Yandex accepted the bounded owner-only test with
  post-DATA SMTP `250 2.0.0`; Mail.ru accepted its bounded owner-only test with
  post-DATA SMTP `250`; both Message-IDs were found in Sent. The queue worker
  was not started for these sends, and business/queue counts stayed unchanged.
  Both outgoing switches were returned to disabled afterward. The owner then
  independently confirmed receipt in both target Gmail mailboxes.
- Next step: none for this finding. The broader active task remains open for
  its separately listed UI/AI/commit work.

## FINDING-024 — `refresh_bad_global_supplier_names` cannot run on production: `CHECKO_KEY` not in Vercel env

- ID: `FINDING-024`
- Severity: `MEDIUM`
- Status: `OPEN — needs owner action`
- Evidence: `POST /maintenance/refresh-bad-global-supplier-names-20260911`
  called against production 2026-09-11 returned
  `{"ok": true, "checked": 0, "fixed": 0, "checko_unavailable": true}`.
  `env -u HTTP_PROXY -u HTTPS_PROXY -u NO_PROXY vercel env ls production`
  confirms no `CHECKO_KEY` variable exists in the Vercel project, even
  though it is present in the local (gitignored) `.env`.
- Impact: `global_suppliers.name` rows already frozen on a bad value from
  before the `trusted_name` guard (DECISION-021) exist on production right
  now and cannot self-heal via this route until the key is configured.
  `suppliers.name` is unaffected (its own backfill,
  `/maintenance/backfill-placeholder-supplier-names-20260911`, needs no
  external API and already ran — 213 rows fixed 2026-09-11).
- Why deferred: Adding a secret to a third-party deployment platform is not
  something an agent should do unilaterally — this needs the owner (or an
  explicit owner instruction with the value) to add it via `vercel env add`
  or the Vercel dashboard.
- Next step: owner adds `CHECKO_KEY` to the Vercel production environment,
  then re-run the maintenance route (owner-only, session+CSRF gated, same
  pattern as the other `/maintenance/*` routes already used this session).

## FINDING-023 — Checko/DaData caching terms of service not verified before `canonical_companies` write-through

- ID: `FINDING-023`
- Severity: `MEDIUM`
- Status: `OPEN — accepted risk, needs a real check`
- Evidence: DECISION-022 added a cross-tenant cache
  (`canonical_companies`) that stores Checko/DaData-sourced company facts
  beyond the single workspace that fetched them, for reuse by any other
  SupplyDesk workspace. Before shipping this, `WebSearch` and `WebFetch`
  were attempted to check Checko's terms of service on storing/caching API
  responses; both tools returned an infrastructure-level error
  (`"issue with the selected model (qwen/qwen3.7-flash)"`) unrelated to the
  query itself, so the check could not be completed. Shipped anyway with
  the owner's implicit acceptance (this is an internal-product cache, not
  redistribution to third parties, a generally defensible pattern for a
  paid-API-backed SaaS) — but this is a business/legal risk decision, not a
  confirmed-compliant fact.
- Impact: If Checko's actual terms prohibit this kind of cross-account
  internal caching, `canonical_companies` and the `_resolve_missing_inn`
  read-path that skips a live Checko call would need to be disabled or
  redesigned (e.g. per-workspace TTL forcing a fresh call regardless of the
  cache).
- Why deferred: Tooling failure, not a skipped step — retrying is the
  correct next action, not silently assuming either outcome.
- Next step: retry the ToS check once WebSearch/WebFetch are working again,
  or have a human read Checko's/DaData's current API terms directly and
  report back.

## FINDING-022 — `canonical_companies` cache only wired into one enrichment stage

- ID: `FINDING-022`
- Severity: `LOW`
- Status: `OPEN — accepted scope boundary, not urgent`
- Evidence: `_resolve_missing_inn` (`backend/domain/supplier_enrichment/
  orchestrator.py`) reads `canonical_companies` before calling
  `checko.lookup()`/`.finances()` and skips both when another workspace
  already resolved the ИНН (proven by
  `tests/test_canonical_companies_cache_reuse.py`). The main
  registry-resolution pipeline (`_process_enrich_step` and its `_resume_*`
  methods, the primary path a fresh search request goes through) does not
  read the cache at all — every workspace still pays for its own Checko
  calls there, even for a company `canonical_companies` already has.
- Impact: The cost-saving goal ("User B reusing what User A already found")
  is only realized for the secondary/retry `_resolve_missing_inn` path, not
  the primary enrichment flow most requests actually go through — so actual
  savings in production are much smaller than the invariant's intent.
- Why deferred: Wiring the primary pipeline (`_process_enrich_step`'s
  registry-resolution branch, ~line 300-400 of orchestrator.py) is
  substantially higher regression risk than the isolated
  `_resolve_missing_inn` function — it is the central path every request's
  search depends on, and modifying it without the same level of test
  coverage this task already built risks a real production regression in
  search/enrichment for every workspace, not just a missed cost-saving.
- Next step: a dedicated follow-up task, scoped and reviewed on its own,
  should wire the same `lookup_canonical_company`-before-`checko.lookup()`
  pattern into `_process_enrich_step`'s registry stage, with its own RED-to-
  GREEN test coverage against that specific code path.

## FINDING-021 — Selecting many AI-context siblings at once causes transient 500s on `/api/mail/threads`

- ID: `FINDING-021`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: Live production verification of the AI-context feature
  (`frontend-v2/src/pages/Messages.tsx`, request "Печь-камин — глубокий
  поиск 20", `request_id=1059`, 126 sibling suppliers) using «Выбрать всех
  поставщиков по заявке» produced roughly 60 `500` responses out of ~126
  parallel `GET /api/mail/threads?request_id=1059&supplier_id=<N>` calls
  (browser network log, this session). Manually re-requesting one of the
  failed `(request_id, supplier_id)` pairs immediately afterward returned a
  clean `200` with correct data — the endpoint and the data are fine; the
  failures were transient and load-related, not deterministic per-supplier.
- Impact: The `aiExtraThreadIds` effect in `Messages.tsx` (fetches
  `api.threadMessages` for every newly selected sibling with no batching or
  concurrency limit) fires one request per selected supplier simultaneously.
  At small selections (a handful of suppliers) this is invisible; at the
  scale of a large deep-search campaign (100+ suppliers) a meaningful
  fraction of those fetches transiently fail, most likely from the
  serverless function's Postgres connection pool being exhausted by the
  burst. The UI has no retry for a failed per-sibling fetch, so some
  suppliers silently contribute an empty transcript to the AI context
  instead of their real last message.
- Why deferred: Unrelated to the task that found it (AI-context scoping to
  suppliers with real communication, and the Messages "Заметки" → supplier
  card change — neither touches this fetch-on-select effect or the
  `/api/mail/threads` endpoint). Root cause (connection pool limit vs. some
  other serverless concurrency ceiling) was not investigated. Fixing this
  needs a deliberate choice (client-side batching/concurrency cap, a
  bulk-fetch endpoint, or per-item retry) that should not be made as a
  side effect of a different task (`ai/AI_CONTRACT.md` rule 5).
- Suggested next step: reproduce deliberately with a controlled concurrency
  count to confirm the ceiling, then either cap `Promise`-style concurrency
  client-side (e.g. small batches) or add a bulk endpoint
  (`request_id` + `supplier_ids[]` → messages) so a "select all" on a large
  campaign is one request instead of N.

## FINDING-020 — No test coverage for `SupplierHandler`'s 404/SPA-fallback routing

- ID: `FINDING-020`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: While extracting `AuthHandlerMixin` from `SupplierHandler`
  (`TASK-BOUNDED-SUPPLIER-APP-AUTH-EXTRACT-20260903`), a search of the
  official test suite for `404`/unknown-route/SPA-fallback assertions found
  zero matches (`grep -rn "404" tests/*.py` — no results). Login/session/
  CSRF/`auth/me` ARE genuinely covered
  (`tests/test_mail_integrity.py::test_session_renews_on_activity_and_survives_repository_restart`,
  `tests/test_outgoing_safety.py::test_owner_endpoint_requires_csrf_confirmation_and_explicit_owner`,
  etc.), but the "unknown `/api/*` path returns 404" and "non-API path falls
  back to the SPA shell" behaviors in `do_GET`/`send_head`/`_serve_app_shell`
  have no direct regression test.
- Impact: A future change to `do_GET`'s fallthrough logic (e.g. reordering
  branches, changing the final `else`) could silently break the 404/SPA
  contract with no test catching it.
- Why deferred: `do_GET`/`do_POST`/`do_DELETE` and their routing logic were
  explicitly NOT touched by the auth-extraction task that found this — only
  auth-related sub-methods (`_login`, `_require_session`, etc.) were moved.
  Writing a route-matrix test for code that wasn't changed is out of that
  task's scope (`AI_CONTRACT.md` rule 5 — do not fix unrelated problems);
  the owner's own instruction for that task also explicitly said not to
  build a large route matrix without necessity.
- Next verification: A separate task adds a small number of targeted tests
  (unknown `/api/*` → 404, non-API path → SPA shell, source-like path →
  404) the next time `do_GET`'s routing is itself the subject of a change.

## FINDING-019 — `diagnostic_runner.py`'s secret scan crashes on a Cyrillic staged diff

- ID: `FINDING-019`
- Severity: `LOW`
- Status: `RESOLVED — fixed by adding explicit encoding="utf-8", errors="replace"
  to the four affected subprocess.run calls, matching the file's own
  existing correct pattern in run_process()`
- Evidence: `scripts/diagnostics/diagnostic_runner.py:secret_path_check` calls
  `subprocess.run(["git", "diff", "--cached", "--unified=0"], ...,
  capture_output=True, text=True, check=False).stdout` (line 580) without an
  explicit `encoding=`. On this Windows environment, `text=True` decodes
  the subprocess's stdout using the locale's default codepage (`cp1251`),
  not UTF-8 — but `git diff` always emits UTF-8. When the currently staged
  diff (`git diff --cached`) contains Cyrillic text (extremely common in
  this codebase's comments/docstrings/Russian identifiers), the reader
  thread hits `UnicodeDecodeError` internally and `.stdout` ends up `None`;
  `scan_staged_literal_diff` then calls `diff_text.splitlines()` on `None`
  and raises `AttributeError`. Reproduced deterministically during
  `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903` while a large,
  Cyrillic-heavy diff was staged-but-uncommitted:
  `tests.diagnostics.test_diagnostic_negative_fixtures.DiagnosticNegativeFixtureTests.test_machine_output_fields_are_present_and_safe`
  errored with exactly this traceback; the same three `subprocess.run` calls
  in the same function (lines 572, 574, 576, for `git diff --name-only`/
  `git ls-files`/`git ls-files --others`) share the same missing-`encoding`
  pattern and are equally exposed, just less likely to contain Cyrillic
  bytes in a single run.
- Impact: any contributor who runs the full local test suite
  (`scripts/run_test_suite.py`) while they happen to have a Cyrillic-containing
  diff staged-but-not-yet-committed will see this test error, indistinguishable
  at a glance from a real regression, purely because of ambient git index
  state rather than anything in the code under test.
- Why deferred: discovered incidentally while verifying
  `TASK-BOUNDED-ROOT-REFACTOR-TESTS-LEGACY-20260903`'s regression suite
  (converting root manual test scripts to `unittest.TestCase`s); fixing a
  subprocess-encoding bug in an unrelated diagnostic tool is out of that
  task's scope (`AI_CONTRACT.md` rule 5 — do not fix unrelated problems).
  Confirmed non-blocking for that task: after the task's own changes were
  committed (clearing the git staging area), a clean rerun of
  `scripts/run_test_suite.py` returned to the established `9`-error
  `pwsh`-gap baseline with no `AttributeError`.
- Next verification (superseded by resolution below): a separate task adds
  `encoding="utf-8"` to all four `subprocess.run(..., text=True, ...)` calls
  in `secret_path_check`
  (`scripts/diagnostics/diagnostic_runner.py:572,574,576,580`), then proves
  the fix by staging a disposable Cyrillic-containing change and confirming
  `test_machine_output_fields_are_present_and_safe` passes instead of
  erroring.
- Resolution: `TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903`
  added `encoding="utf-8", errors="replace"` to the four `secret_path_check`
  calls (lines 572, 574, 576, 580) — matching the exact parameters this same
  file's own `run_process()` helper already used correctly a few lines
  above, so this was a real inconsistency, not a new pattern. Also fixed two
  more instances of the identical missing-`encoding` defect found in the
  same file while verifying the fix (`git_check`'s raw `branch`/`head`
  lookups at lines 133-134) — lower practical risk since branch names and
  commit hashes are normally ASCII, but the same root cause. Proven by
  staging this task's own Cyrillic-heavy documentation changes (this file
  and the task report) and confirming
  `test_machine_output_fields_are_present_and_safe` passes with the fix in
  place, where it previously raised `AttributeError` under the same staged
  condition.
- Resolution report:
  `ai/reports/TASK-FIX-FINDING-019-DIAGNOSTIC-RUNNER-ENCODING-20260903-report.md`

## FINDING-018 — `collect_inn.py --llm` imports a nonexistent symbol

- ID: `FINDING-018`
- Severity: `LOW`
- Status: `RESOLVED — fixed with a RED-to-GREEN bug-workflow proof; see resolution below`
- Evidence: `TASK-BOUNDED-ROOT-REFACTOR-LLM-20260902`'s fresh reference scan
  found `collect_inn.py:217` does `from llm_fallback import InnLlmExtractor,
  api_key_present` (now `from backend.integrations.llm.llm_fallback import
  InnLlmExtractor, api_key_present`), but `llm_fallback.py` only ever
  defined `LlmExtractor`, never `InnLlmExtractor`. This predates the move —
  confirmed by checking the pre-move file content — and the move preserves
  the identical `ImportError` from the new path. The same code path's error
  message also tells the operator to set `ANTHROPIC_API_KEY`, while the
  actual `api_key_present()` checks `ROUTERAI_KEY`.
- Impact: `python collect_inn.py --llm ...` raises `ImportError` immediately
  when the `--llm` flag is used; the feature is currently non-functional.
  No test exercises this path (env/flag-gated), so nothing else would catch
  it.
- Why deferred: out of scope for a structural move task
  (`AI_CONTRACT.md` rule 5 — do not fix unrelated problems); `collect_inn.py`
  was explicitly limited to an import-line change only.
- Next verification (superseded by resolution below): a separate task
  confirms whether `InnLlmExtractor` was meant to be `LlmExtractor`, fixes
  the symbol reference and the `ANTHROPIC_API_KEY`/`ROUTERAI_KEY` mismatch,
  and adds coverage for `--llm` that does not require a live key.
- History/intent check: `git log --all -S InnLlmExtractor` shows exactly one
  matching commit — the repository's initial bulk import — meaning
  `InnLlmExtractor` was never a real class anywhere in this repo's tracked
  history. `Documents/28-8/enrichment-and-cache.md` (existing product
  documentation, written independently of this finding) already recorded it
  as "осталось от версии до перехода на RouterAI" (a leftover from the
  pre-RouterAI version) and confirmed the web pipeline's own
  `_enrich_suppliers` already correctly uses `LlmExtractor`/`ROUTERAI_KEY`.
  So `LlmExtractor` is confirmed as the intended current implementation, not
  a guess.
- Resolution: `TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902` reproduced the
  bug deterministically (a behavioral reproducer calling the real
  `collect_inn.main(["...", "--llm"])` failed with the exact predicted
  `ImportError: cannot import name 'InnLlmExtractor'`, before any
  network-capable code ran), then applied the minimal fix: `collect_inn.py`
  now imports `DEFAULT_MODEL, LlmExtractor, api_key_present`, constructs
  `LlmExtractor(model=args.llm_model or DEFAULT_MODEL)` (matching the
  existing safe pattern in `scripts/collect_contacts.py`, so `--llm-model`
  never resolves to `None`), and the missing-key message now names RouterAI
  and `ROUTERAI_KEY`. The same reproducer then passed (`GREEN`) —
  `FIX_PROVEN`. No prompts, schemas, `DEFAULT_MODEL` value, or provider
  behavior changed; `0` external provider calls throughout.
- Resolution report:
  `ai/reports/TASK-FIX-FINDING-018-COLLECT-INN-LLM-20260902-report.md`

## FINDING-003 — Standard helper-script coverage is incomplete

- ID: `FINDING-003`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The canonical baseline documents the tracked operator-tool set but does not establish a complete standard helper-script catalog.
- Impact: Future agents may repeat ad-hoc inspection or use inconsistent commands.
- Why deferred: This task establishes governance; it does not add application or operator behavior.
- Next verification: Compare the required diagnostic control-plane command catalog with tracked scripts in a separately scoped task.

## FINDING-004 — Source checkout has broad pre-existing worktree changes

- ID: `FINDING-004`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical baseline records a dirty source checkout and intentionally isolates governance work in a clean control worktree.
- Impact: Source-side ownership and rollback cannot be inferred from the governance branch.
- Why deferred: Resolving ownership would require user decisions about pre-existing application changes.
- Next verification: Owner reviews source `git status`, tracked/untracked inventory, and the exact allowlist before any cleanup or merge.

## FINDING-006 — Historical published-environment backend failures

- ID: `FINDING-006`
- Severity: `MEDIUM`
- Status: `SUPERSEDED`
- Evidence: The old published audit run recorded failures, while the canonical control baseline recorded `373 passed, 1 skipped, 0 failed, 0 errors` in its controlled run.
- Impact: The old failure count must not be presented as the current control baseline or as proof of an application fix.
- Why deferred: The environments are not equivalent and this task did not rerun live backend acceptance.
- Next verification: Re-run the relevant backend-backed live routes in the approved runtime environment and compare scope explicitly.

## FINDING-008 — Unattributed source-side API edit

- ID: `FINDING-008`
- Severity: `HIGH`
- Status: `OPEN`
- Evidence: The canonical baseline records an unattributed `api/index.py` worktree edit in the source checkout.
- Impact: Ownership and deployability of the source-side API change are unknown.
- Why deferred: This task forbids application edits and cannot assign ownership to another agent.
- Next verification: Source owner identifies the change, validates it against the source HEAD, and decides whether to keep, revert, or isolate it.

## FINDING-009 — Local credential-bearing environment risk

- ID: `FINDING-009`
- Severity: `P2`
- Status: `OPEN`
- Lifecycle: `DEFERRED_SECURITY_ACTION — LOCAL_ARCHIVE_SECRET_RETENTION`
- Cleanup impact: `CLEANUP_PHASE: COMPLETE` — this deferred security action
  does not keep the recovery/cleanup phase open.
- Evidence: The canonical checkout still has no current operational
  `.env`/`.env.*` files, no tracked operational secret paths and no operational
  `.env` path in Git history. Three unique historical `.env.example` blobs were
  classified as `SAFE_TEMPLATE`. The controlled allowlist review covered 12
  snapshot `.env*` files and 12 quarantine token/auth-named artifacts: 8 were
  `REAL_SECRET_PRESENT`, 4 were `MIXED`, 6 were `EMPTY_OR_NON_SECRET`, 5 were
  `SAFE_TEMPLATE`, and 4 were `UNDETERMINED`.
- Git exposure: `NO`. The real or mixed files are retained in external
  snapshots/quarantine, outside the canonical Git repository. Five paired
  snapshot paths are identical copies across the two baseline containers;
  quarantine production OAuth state files are distinct.
- Impact: Accidental staging or publication could disclose credentials or enable external actions.
- Review result: `SECURITY_REVIEW_REQUIRED` — real and mixed secret-bearing
  material was found in local archive retention, and four binary/image artifacts
  remain `UNDETERMINED`.
- Why deferred: The review did not alter the retained files. No deletion,
  rotation, copying, external transmission or Git history rewrite was
  performed.
- Required action: `KEEP_PROTECTED` until owner approval; then
  `DELETE_AFTER_OWNER_APPROVAL` for unneeded retained copies and
  `ROTATE_CREDENTIAL` only where the owner confirms a credential is current or
  may have been exposed. `HISTORY_REWRITE_REVIEW` is not indicated because Git
  secret exposure is `NO`.
- Next verification: Owner approves retention cleanup and confirms credential
  ownership/validity; separately resolve the four `UNDETERMINED` artifacts.

## FINDING-015 — Residual repository-hygiene audit drift

- ID: `FINDING-015`
- Severity: `MEDIUM`
- Status: `OPEN`
- Evidence: The retained audit index records remaining `AUDIT-002` through `AUDIT-011` findings.
- Impact: Repository hygiene, tooling, and source-state questions remain visible follow-up work.
- Why deferred: This task only establishes documentation ownership and retention; it must not broaden into cleanup or application repair.
- Next verification: Triage each retained audit finding in a separate task with an explicit allowlist and rollback plan.

## FINDING-017 — `checko_client.py` move blocked by an immutability protected-path list

- ID: `FINDING-017`
- Severity: `LOW`
- Status: `RESOLVED — checko_client.py moved and the immutability guard migrated
  to the new path in the same change`
- Evidence: `TASK-BOUNDED-ROOT-REFACTOR-REGISTRY-20260902`'s fresh reference
  scan found `supplier_discovery_v2/immutability_check.py:16` hardcodes a
  repository-root-relative `"checko_client.py"` entry in its
  `protected_paths()` tuple, used to hash-verify that named files have not
  drifted. No committed/tracked `protected_manifest.json` baseline exists in
  this checkout, so nothing currently breaks, but moving `checko_client.py`
  out of root would silently drop it from future `--write-baseline` snapshots
  (the function guards each candidate with `.is_file()`) and would make any
  externally held baseline report it as `changed` on next `verify()`. This
  was not in the prior `TASK-PYTHON-ROOT-DIAGNOSTIC-20260902` reference list.
  `CLAUDE.md`'s Project layout section also names `checko_client.py` as an
  intentional root example, consistent with this being live structure, not
  an oversight.
- Impact: Moving `checko_client.py` to
  `backend/integrations/registry/checko_client.py` (the diagnostic's
  `MOVE_INTEGRATIONS` recommendation) requires either updating
  `supplier_discovery_v2/immutability_check.py`'s protected-path list or an
  explicit decision that Checko is no longer immutability-protected —
  `supplier_discovery_v2/` is out of scope for a bounded CLI/registry-move
  task, per that task's own "DO NOT TOUCH" boundary.
- Why deferred: The registry-move task moved only `dadata_client.py` (not
  referenced anywhere in `immutability_check.py`) and left `checko_client.py`
  at root rather than silently weakening an existing safety mechanism or
  reaching into a directory explicitly marked out of scope.
- Next verification (superseded by resolution below): a separate task scoped
  to touch both `checko_client.py` and
  `supplier_discovery_v2/immutability_check.py` together.
- Resolution: `TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902`
  moved `checko_client.py` to
  `backend/integrations/registry/checko_client.py` and, in the same change,
  updated `supplier_discovery_v2/immutability_check.py:protected_paths()` to
  protect the new path instead of the old root path. A fresh baseline
  generated against the moved tree verifies clean (`[]`); a disposable
  synthetic copy of the new path, mutated after baselining, is correctly
  reported as changed. `checko_client.py` was never dropped from protection
  at any point in the same commit.
- Resolution report:
  `ai/reports/TASK-CHECKO-REGISTRY-MOVE-IMMUTABILITY-MIGRATION-20260902-report.md`

## FINDING-016 — Frontend candidates remain review-required

- ID: `FINDING-016`
- Severity: `LOW`
- Status: `OPEN`
- Evidence: The isolated Knip audit reported `RiskFactors.tsx`, three manual
  Playwright/Lighthouse configuration files and the direct `lighthouse`
  development dependency as candidates.
- Impact: The repository retains a small amount of potentially unused
  frontend/tooling surface; deleting it without owner review could remove a
  manual acceptance path or planned UI component.
- Why deferred: The approved Batch 2 allowlist authorized only the proven
  Python cleanup. No frontend file or dependency was deleted.
- Next verification: Owner approves a separate frontend/dependency allowlist;
  repeat clean install, reference/build analysis and full browser acceptance
  before any deletion.

