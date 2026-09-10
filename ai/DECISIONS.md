---
document_id: DECISIONS-001
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-01
source_commit: 84083130e3a75eb5a6d4fa83957db6760724379b
---

# Decisions

This is the concise current decision register. It is not an infinite event
log. Superseded and older decision prose is preserved in
[`ai/history/2026/09/DECISIONS-CHRONICLE-20260901.md`](history/2026/09/DECISIONS-CHRONICLE-20260901.md).

## DECISION-022 — Cross-tenant canonical company directory (`canonical_companies`)

- Decision ID: `DECISION-022`
- Date: `2026-09-11`
- Status: `ACTIVE`
- Context: The owner asked for a "единая база поставщиков" so a company
  discovered by one SupplyDesk customer (workspace) doesn't get re-searched
  and re-enriched from scratch by another. Clarified explicitly (asked via
  AskUserQuestion, since this changes architecture and touches data privacy
  across accounts): the owner confirmed this means genuine cross-tenant
  reuse, not just the existing per-workspace `global_suppliers` dedup.
- Decision: Added `canonical_companies` (+ `canonical_company_finance_history`,
  `canonical_company_risks`; `migrations/038_canonical_companies.sql`) as the
  one table cluster in the project with no `workspace_id`. It holds only
  general, public company facts (ИНН/ОГРН/name/site/public contact/registry
  status/finance history/risks/source/timestamps) — never a workspace's
  relationship to a supplier, communication, notes, prices, or anything else
  currently scoped to a tenant. `apply_supplier_enrichment` writes through to
  it whenever it resolves a real company (trusted source, same trust
  boundary as `trusted_name=True`). `_resolve_missing_inn`
  (`backend/domain/supplier_enrichment/orchestrator.py`) reads from it before
  spending a live Checko `lookup()`/`finances()` call for an ИНН another
  workspace already resolved.
- Reason: This is the minimum real "identity resolution + reuse" layer that
  satisfies the owner's cost concern (User A resolves `keramstroi.ru`, User B
  later discovering the same company reuses the result) while keeping every
  other table's tenant isolation completely unchanged — proven by
  `tests/test_canonical_companies.py::test_write_through_carries_no_tenant_specific_data`
  asserting the exact allowed field set.
- Consequences: A workspace's enrichment can now silently get faster/cheaper
  for a company another (unrelated) workspace already resolved. Checko/
  DaData-sourced facts about a company are now retained beyond the single
  workspace that fetched them, for reuse by any other SupplyDesk workspace.
- Non-goals / explicitly NOT done: only one enrichment stage
  (`_resolve_missing_inn`) reads the cache — the larger registry-resolution
  pipeline (`_process_enrich_step` and friends) does not yet; deduplication
  by domain (not just ИНН) is not implemented; no TTL/staleness policy
  exists yet (see `docs/domain/SUPPLIER_MODEL.md` §5) — every canonical row
  is treated as always-valid once written. **Checko/DaData's terms of
  service on caching/storing their API responses were not verified** (tool
  failure — WebSearch/WebFetch were unavailable in this session) before
  shipping the write-through; this is a real compliance risk the owner
  should confirm or have someone confirm before this reuse path handles
  meaningful volume.
- Related: `docs/domain/SUPPLIER_MODEL.md` §1, §6; `mail/canonical_companies.py`.

## DECISION-021 — AI-context and supplier-name invariants for Messages/supplier model

- Decision ID: `DECISION-021`
- Date: `2026-09-11`
- Status: `ACTIVE`
- Context: The owner reported (a) the AI-помощник's selectable/sent context
  on `/messages` still included every supplier of a request regardless of
  whether they had actually replied, and (b) supplier display names still
  showed raw SERP-result titles (e.g. "Купить печь-камин для дома и дачи,
  цены") instead of company names, after an earlier pass only partially
  addressed both. Root-caused precisely this time: (a) the prior fix used
  "any communication" (`messages_count > 0`) instead of "has replied", and
  (b) two separate write paths could each independently clobber a
  once-resolved real name with a placeholder (`upsert_supplier`'s
  unconditional `ON CONFLICT` overwrite, and
  `_get_or_create_global_supplier`'s fill-only-if-empty guard combined with
  the manual-ИНН-entry path seeding it with an unenriched name first).
- Decision: Two durable product invariants, detailed in
  `docs/ui/MESSAGES_SCREEN_SPEC.md` §7 and `docs/domain/SUPPLIER_MODEL.md`
  §3 respectively:
  1. **AI-context invariant**: only suppliers of the current request with
     `threadResponseStatus === 'answered'` ("Есть ответ") are eligible for
     AI-помощник context — not "any communication attempt". Enforced at
     three independent points in Messages.tsx (selectable pool, checkbox
     visibility, and the actual payload-construction site), not just a UI
     filter.
  2. **Supplier-name invariant**: a supplier's display name must come from
     resolved company data (registry/Checko/LLM, always paired with a
     resolved ИНН) or a previously-normalized name, never automatically from
     a page `<title>`, SEO description, ad H1, or email subject. A
     placeholder-quality write (host-equal or empty) must never overwrite an
     already-real name at either `suppliers.name` or `global_suppliers.name`.
- Reason: Both bugs are structural (write-path/query-path logic), not data
  issues — a per-record manual fix would have recurred. Fixing only the
  visible symptom (a UI filter, or renaming individual bad records) was
  explicitly rejected per the owner's instruction; both fixes are guarded at
  the actual write sites and proven RED-to-GREEN
  (`tests/test_supplier_name_resolution.py`).
- Consequences: `upsert_supplier` and `_get_or_create_global_supplier` (both
  `mail/repository.py`) now guard every future name write against
  downgrading an existing real name. Two owner-only one-time maintenance
  routes exist for already-affected data:
  `/maintenance/backfill-placeholder-supplier-names-20260911` (run on
  production 2026-09-11, 213 rows fixed) and
  `/maintenance/refresh-bad-global-supplier-names-20260911` (blocked on
  production — `CHECKO_KEY` is not configured in the Vercel environment;
  code is tested but has not run against real data yet).
- Non-goals: This does not implement cross-tenant/cross-workspace supplier
  sharing (the owner's "User A / User B" example implies data shared across
  different SupplyDesk accounts, which the existing `global_suppliers` table
  does not do — it is workspace-scoped). See
  `docs/domain/SUPPLIER_MODEL.md` §6 — open question requiring an explicit
  owner decision before any implementation, since it changes architecture
  and cross-tenant data-privacy boundaries.
- Related: `docs/ui/MESSAGES_SCREEN_SPEC.md`, `docs/domain/SUPPLIER_MODEL.md`,
  `ai/DEFERRED_FINDINGS.md` FINDING-021 (unrelated transient 500s found
  during the AI-context live verification).

## DECISION-020 — MagicRings is permanent on the Login screen

- Decision ID: `DECISION-020`
- Date: `2026-09-10`
- Status: `ACTIVE`
- Context: The Login screen's animated `MagicRings` WebGL background
  (`frontend-v2/src/components/MagicRings.tsx`, rendered from
  `frontend-v2/src/pages/Login.tsx`) was replaced once already this
  project by an unrelated recreated design (commit `e7f0d7e`) and reverted
  back (commit `163a4bb`) after the owner explicitly flagged it. The owner
  has since repeated, more than once, that the Login screen must always
  show MagicRings, most recently after observing a login render without it.
- Decision: `MagicRings` is a permanent, required part of the Login screen.
  No future task may remove it, replace it with a static/alternate design,
  or make it optional, without a direct, explicit owner instruction to do
  so in that specific task. `Login.tsx`'s existing `onUnsupported` fallback
  (a static circle shown only when the owner's own browser genuinely lacks
  WebGL) is the one allowed exception and is not itself a removal.
- Reason: This has already regressed once from an agent redesigning the
  login screen without being asked to touch it; the owner does not want to
  keep re-explaining this.
- Consequences: Any task touching `Login.tsx` must leave `MagicRings`
  imported and rendered exactly as-is unless the owner's current
  instruction explicitly asks for a login-screen redesign.
- Non-goals: This does not freeze the rest of Login.tsx (form fields,
  provider buttons, copy) — only the MagicRings background.
- Related commits: `e7f0d7e` (regression), `163a4bb` (revert).

## DECISION-018 — Conversation-first visual hierarchy for `/messages`

- Decision ID: `DECISION-018`
- Date: `2026-09-04`
- Status: `ACTIVE`
- Context: The first `/messages` modernization introduced consistent UI
  primitives, but the screen still carried the visual weight of a legacy CRM:
  requests, messages, statuses, counters and row actions competed equally.
- Decision: Treat the request-linked conversation as the primary product
  object. Keep requests in a left navigator with search, filters and compact
  activity rows; keep supplier, reply state and related request in one compact
  conversation header; render messages as a timeline; reserve the sticky
  footer for one main next step, `Ответить поставщику`. Keep unmatched mail,
  outbox, metadata and delivery recovery as secondary but reachable flows.
- Reason: This changes the user's visual path from scanning a mailbox to
  continuing one procurement conversation, while preserving existing routes,
  semantics and recovery actions. It is a presentation decision, not a new
  data or component architecture.
- Consequences: counts, row metadata controls and repeated statuses no longer
  dominate the list; the linked request is a compact context relationship;
  the visible primary action is stable at the bottom of the conversation.
- Related task: `TASK-SUPPLYDESK-MESSAGES-DEEP-VISUAL-REDESIGN-20260904`.

## DECISION-017 — Procurement workspace layout and user-scoped thread metadata

- Decision ID: `DECISION-017`
- Date: `2026-09-04`
- Status: `ACTIVE`
- Context: The `/messages` page needed to support procurement triage without
  turning correspondence into a generic mailbox. The existing request-grouped
  list, manual unmatched workflow, outbox and delivery safeguards are already
  product contracts and must remain authoritative.
- Decision: Keep a desktop two-column layout (request/supplier navigator plus
  conversation detail) and a list-to-detail mobile layout. Add a compact
  unmatched preview and HTML5 drag-and-drop only as a shortcut into the current
  manual-link workflow. Direct drag linking is allowed only for one exact
  sender match; domain-only, ambiguous and unknown cases require explicit
  manual selection. Store the important marker and priority separately in
  `mail_thread_user_metadata`, keyed by workspace, user, request and supplier;
  they never overwrite mail transport or delivery status.
- Reason: This reuses the existing mail identity and linking APIs, keeps
  decisions reversible, makes shared-workspace presentation personal to the
  operator, and prevents a UI gesture from silently guessing a supplier.
- Consequences: `GET /api/correspondence` and the outbox include the current
  user's metadata; `POST /api/correspondence/metadata` is the single write
  route. A future thread identity change must update this scope deliberately,
  rather than adding a second flag/priority store.
- Related task: `TASK-MESSAGES-WORKSPACE-REDESIGN-20260904`.

## DECISION-016 — Name and separate LOCAL_CANONICAL (port 8000) from SAFE_TEST (port 18000) runtime modes

- Decision ID: `DECISION-016`
- Date: `2026-09-03`
- Status: `ACTIVE`
- Context: A prior session built a "start the server" desktop shortcut wired
  to the `SAFE_TEST` runtime (`scripts/start_test_runtime.ps1`, default port
  `18000`, real provider credentials always blanked) because it was the one
  path already proven working in that session, without re-checking
  `PROJECT_MANIFEST.yaml` (which already listed `backend_default_port: 8000`
  and a separate `browser_acceptance.audit_live_route_url: 18000`, just
  without an explicit rule tying "which mode does the owner actually mean"
  to either). The owner then tried "Sign in with Yandex" against port 18000
  and got Yandex's callback-mismatch error, since the registered OAuth
  redirect URI is for port 8000.
- Decision: `PROJECT_MANIFEST.yaml` gets one new `runtime_modes` block naming
  exactly two mutually exclusive modes — `LOCAL_CANONICAL` (port `8000`,
  `python supplier_app.py`, real credentials via a local `.env` only by
  explicit owner task) and `SAFE_TEST` (port `18000`,
  `scripts/start_test_runtime.ps1 -Apply`, disposable DB, provider
  credentials always blanked by the script itself). This is the first
  source of truth. `docs/operations/runbooks/RUNBOOK-BACKEND-STARTUP.md`
  gives one unambiguous command per mode. `ai/AI_CONTRACT.md` rule 14 now
  requires classifying `RUNTIME_MODE` (`LOCAL_CANONICAL`/`SAFE_TEST`/`CI`/
  `OTHER`) against the manifest before choosing a start command or port, and
  forbids inferring the mode from "whatever already worked earlier in the
  session."
- Reason: the ambiguity was real and already latent in the manifest (two
  ports, no named relationship); the fix reuses the existing
  `LOCAL_CANONICAL` name already used by `scripts/doctor.ps1`'s diagnostic
  profiles (cross-referenced, not duplicated) instead of inventing a new
  term or a new governance subsystem.
- Consequences: any future "start/use the app" request must be classified
  before a script or port is chosen. `SAFE_TEST` must never be offered as a
  substitute for the owner's normal local session, and `LOCAL_CANONICAL`
  must never be used for a test/browser/diagnostic run.
- Related task: `TASK-ROOT-CAUSE-RUNTIME-FIX-20260903`.

## DECISION-015 — Dellin logistics MVP: address-search routing, no workspace_id on logistics_quotes

- Decision ID: `DECISION-015`
- Date: `2026-09-03`
- Status: `ACTIVE`
- Context: `TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903` added a manual shipping-cost
  calculator against the Дeловые Линии (Dellin) public calculator API
  (`https://api.dellin.ru/v2/calculator.json`). The official docs
  (`dev.dellin.ru`) block direct automated fetches (401/bot-block); the
  request/response schema was verified through the public Wayback Machine
  archive of the same official documentation (snapshot `20240221125337`)
  instead of guessing fields or bypassing the site's own protection.
- Decision:
  1. Route input is a free-text city/terminal string per side, sent as
     `delivery.derival/arrival.address.search` with `variant: "address"`.
     The separate terminal-search method
     (`https://api.dellin.ru/v1/public/request_terminals.json`) is
     deliberately **not** implemented — it needs a KLADR city code from yet
     another lookup, which the MVP's manual free-text UI does not need.
  2. `deliveryType.type` is fixed to `"auto"` — the form does not let the
     user pick a delivery mode in this MVP.
  3. `migrations/033_logistics_quotes.sql`'s `logistics_quotes` table has no
     `workspace_id` column; workspace isolation is enforced by joining
     `requests.workspace_id` in every mixin query, the same pattern already
     used by `request_supplier_states`.
  4. `vat_included` is stored as `NULL` (unknown) — the documentation section
     that was actually read does not expose a VAT field; it must not be
     assumed `true`/`false`.
  5. The rate limiter (45/min, 1600/hour) and the input-hash cache both live
     in one process-lifetime `LogisticsQuoteService` instance held by
     `SupplierApp`, not a distributed store — matches the single-process
     local backend and the task's explicit "no Redis/queue" instruction.
- Reason: keeps the MVP to exactly the calculator call the manual-entry UI
  needs, avoids inventing undocumented fields, and reuses an established
  workspace-isolation pattern instead of adding a redundant column.
- Consequences: adding a terminal picker, a delivery-type selector, or a
  distributed rate limiter/cache later is a new, separately scoped task, not
  an extension implied by this one. Commercial authorization to use the
  Dellin API inside a paid SaaS product is `NOT VERIFIED` and is not implied
  by this decision.
- Related task: `TASK-LOGISTICS-DELLIN-QUOTE-MVP-20260903`.

## DECISION-014 — Close the current bounded-refactor series and pause the remaining architecture program

- Decision ID: `DECISION-014`
- Date: `2026-09-03`
- Status: `ACTIVE`
- Context: A read-only recovery audit on `integration/current-architecture-governance-20260903`
  @ `a88334deb59f32d43f79afca63f71fc7bf263da0` found `NO_UNFINISHED_REFACTOR_FOUND`:
  all seven bounded `supplier_app.py`/`mail/repository.py` extraction passes
  reached full close (implement, tests, report, `ACTIVE_TASK: IDLE`) and are
  already integrated; the remaining architecture-program passes (campaign
  lifecycle extraction, queue/send-attempt refactor, inbox-reply refactor,
  `supplier_app.py` mail HTTP batch C, dispatch-table conversion, further
  architecture-enforcement changes) have zero commits anywhere in the
  repository — only prose next-step language in task reports and
  `ai/CURRENT_STATE.md`.
- Decision: The owner declares the current bounded-refactor series closed.
  The remaining architecture program is paused. Neither Codex nor Claude Code
  may start any of the listed paused directions on the basis of
  `ai/CURRENT_STATE.md`, `ai/NEXT_STAGES.md`, a task report, an
  `ai/DEFERRED_FINDINGS.md` entry, or "next step" wording alone. Resumption
  requires a new, direct owner instruction naming a Task ID, scope,
  non-goals, allowed files and acceptance criteria.
- Reason: Prevents an agent from treating documented next-step prose as
  standing authorization, matching the recovery audit's own finding that
  further passes were already scoped by their own reports as requiring a
  separate owner decision.
- Consequences: `ai/ACTIVE_TASK.md` remains `IDLE`. Open `FINDING-*` entries
  in `ai/DEFERRED_FINDINGS.md` remain independent technical debt, are not
  part of this pause, and do not block ordinary product work unless a future
  task's files overlap them. The nine pre-existing `errors=9` in the official
  suite remain unresolved and out of this closeout's scope.
- Related task: `TASK-ARCHITECTURE-REFACTOR-SERIES-PAUSE-20260903`.

## DECISION-013 — Make the workspace gate a pre-analysis stop

- Decision ID: `DECISION-013`
- Date: `2026-09-03`
- Status: `ACTIVE`
- Context: The prior gate was described before mutations and runtime/build
  actions, but a read-only or architecture/cleanup task could begin in the
  wrong checkout. The legacy checkout also had stale adapter instructions.
- Decision: Require `SESSION_WORKSPACE_HARD_GATE` as the first project action,
  including `READ_ONLY`. Permit only root identity, the guard, the canonical
  pointer and a legacy marker before the gate; a failed guard is a hard stop.
  Keep the physical canonical workspace stable while treating branch identity
  as task-dependent. Update the legacy adapter/marker locally without
  synchronizing the legacy checkout into the canonical branch.
- Reason: It prevents analysis and tool selection from operating on a stale or
  user-modified checkout, while preserving explicit worktree/CI use through
  `-ExpectedRoot`.
- Consequences: Wrong-root read-only audits are intentionally blocked; a fresh
  Claude proof remains unavailable while its non-interactive API harness
  returns malformed HTTP 200 responses. No product behavior changes.
- Related task: `TASK-COLD-START-WORKSPACE-HARD-GATE-20260903`.

## DECISION-012 — Make the project operating model the default agent contract

- Decision ID: `DECISION-012`
- Date: `2026-09-03`
- Status: `ACTIVE`
- Context: The project had canonical preflight, tool-selection, verification and
  delivery rules, but ordinary prompts could still be interpreted as requiring
  the owner to repeat tool names or approve direct causal updates.
- Decision: After successful Session Preflight, agents inherit the canonical
  project operating model for the healthy session. The agent selects the
  minimum sufficient tools, expands only direct causal dependencies, continues
  delivery under the declared mode, and stops for real owner decisions only.
  The full behavior is owned by `ai/VIBECODING_RULES.md`; `ai/AI_CONTRACT.md`
  keeps the compatibility pointer and safety boundary.
- Reason: One canonical default removes repeated prompt boilerplate while
  preserving destructive, security, live-external and upstream approval gates.
- Consequences: A neutral fresh-session canary is required to prove behavior;
  static policy consistency alone cannot be reported as universal behavioral
  proof. The existing browser split, Code Rot role, Bug Reproducer gates,
  Skill Doctor periodic policy and tool-usage reporting remain unchanged.
- Related task: `TASK-DEFAULT-AGENT-OPERATING-MODEL-20260903`.

## DECISION-011 — Keep architecture lifecycle and browser auth boundaries explicit

- Decision ID: `DECISION-011`
- Date: `2026-09-02`
- Status: `ACTIVE`
- Context: Root growth, stale replacement copies, unclear component retirement
  and unsafe assumptions about owner login were separate recurring review
  risks.
- Decision: Use the shared AI contract for architecture placement and lifecycle
  rules, one component registry under `docs/architecture/`, and a local-only
  headed Playwright auth handoff in the frontend runbook. Remote CI must use an
  isolated account, seeded session or controlled fixture and must not wait for
  an owner login.
- Reason: The boundaries address the cross-cutting risks without changing
  product behavior, current browser tests, CI routing or repository structure.
- Consequences: New source placement and retained non-active components need
  explicit records; the existing `/login` public-shell timeout remains a
  request/network diagnosis item, not an auth handoff request.
- Related task: `TASK-ARCHITECTURE-HYGIENE-LIFECYCLE-AUTH-HANDOFF-20260902`.

## DECISION-010 — Reuse verified session context with cheap task checks

- Decision ID: `DECISION-010`
- Date: `2026-09-02`
- Status: `ACTIVE`
- Context: Sequential agent tasks were repeating full governance and
  environment discovery even when the workspace and instructions were
  unchanged.
- Decision: Run one `SESSION PREFLIGHT` per healthy agent session, a cheap
  `TASK PREFLIGHT` for each new independent task, and only action-specific
  checks for a continuation. Revalidate on workspace, Git-root, environment,
  instruction or context changes. Load skills lazily, apply a change budget,
  and update state documents only when their facts are affected.
- Reason: Deterministic safeguards remain in place while avoidable repeated
  reading and unrelated checks stop consuming task time.
- Consequences: No persistent session database or orchestration service is
  introduced. The workspace guard and existing high-risk controls remain
  mandatory and available.
- Related task: `TASK-VIBECODING-EXECUTION-OVERHEAD-OPTIMIZATION-V1-20260902`.

## DECISION-009 — Enforce an explicit workspace boundary

- Decision ID: `DECISION-009`
- Date: `2026-09-02`
- Status: `ACTIVE`
- Context: A backend process was confirmed in the legacy OneDrive checkout,
  while the canonical checkout had no executable workspace guard.
- Decision: Default local control tooling accepts only
  `C:\Users\edwat\SupplyDesk`. CI and intentional Git worktrees must pass the
  exact absolute root through `-ExpectedRoot`; arbitrary `SupplyDesk_*`
  discovery is forbidden.
- Reason: A guard can stop the wrong checkout before files, runtime, tests,
  databases or Git publication are changed without changing directory or
  branch automatically.
- Consequences: Legacy `C:\Users\edwat\OneDrive\Документы\ChatGPT\SaaS` is
  recovery-only; portable CI/worktree execution remains available through an
  explicit override.
- Related task: `TASK-CANONICAL-WORKSPACE-GUARD-V1-20260902`.

## DECISION-006 — One canonical current-state source

- Decision ID: `DECISION-006`
- Date: `2026-09-01`
- Status: `ACTIVE`
- Context: Multiple state-like files and old snapshots made chronology look current.
- Decision: `ai/CURRENT_STATE.md` is the only canonical current-state source.
- Reason: Agents need one short, evidence-backed state snapshot with explicit limitations.
- Consequences: Other state-like documents must be supporting, historical, task evidence, or explicitly non-canonical.
- Related requirements: `TASK-DOCUMENTATION-GOVERNANCE-20260901`, canonical baseline control contract.
- Related commits: `792f441b4b6099533177e7c1d23d6252670f9309`.

## DECISION-007 — Separate operational control from product documentation

- Decision ID: `DECISION-007`
- Date: `2026-09-01`
- Status: `ACTIVE`
- Context: AI state, task locks, audits, and product explanations were mixed across roots.
- Decision: `ai/**` owns operational control; `docs/**` owns product requirements, architecture, API, data, testing, and operations documentation.
- Reason: The two sets have different freshness, ownership, and evidence rules.
- Consequences: `docs/**` has no independent current-state source; it links to `../ai/CURRENT_STATE.md` when current context is needed.
- Related requirements: `TASK-DOCUMENTATION-GOVERNANCE-20260901`, documentation lifecycle policy.
- Related commits: `792f441b4b6099533177e7c1d23d6252670f9309`.

## DECISION-008 — Keep audit evidence remotely, retain a canonical pointer

- Decision ID: `DECISION-008`
- Date: `2026-09-01`
- Status: `ACTIVE`
- Context: The canonical branch contained a full forensic audit bundle while a dedicated audit branch already retained it.
- Decision: Keep the audit index, summary, final report, important findings, and a remote pointer in the canonical branch; remove only heavy forensic duplicates from this governance branch after remote proof.
- Reason: Reviewers retain traceability without bloating the working control branch.
- Consequences: The audit branch and history remain authoritative for raw evidence; the canonical branch records the exact ref and commit.
- Related requirements: `TASK-DOCUMENTATION-GOVERNANCE-20260901`, `ai/AUDIT_POLICY.md`.
- Related commits: `b5a454f9b39f3cbf01d640d5b67e4231ca25733a`.

## DECISION-004 — Correspondence semantics remain explicit

- Decision ID: `DECISION-004`
- Date: `2026-08-30`
- Status: `ACTIVE`
- Context: Requests, contacts, attempts, and provider acceptance are different entities.
- Decision: Documentation must keep those entities and their counts separate.
- Reason: Collapsing them creates unsafe operational claims.
- Consequences: Reports and current state must name the counted entity and evidence source.
- Related requirements: mail and campaign documentation contract.
- Related commits: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`.

## DECISION-019 — Hard runtime selection by purpose

- Decision ID: `DECISION-019`
- Date: `2026-09-04`
- Status: `ACTIVE`
- Context: Multiple backend, Vite, Playwright and visual-acceptance commands
  could select a port by convention, including a previous automatic fallback
  from canonical `:8000` to disposable `:18000`.
- Decision: `scripts/runtime_guard.py` is the single runtime-selection
  authority. `OWNER_SESSION`, `VISUAL_ACCEPTANCE`, `OAUTH_CHECK` and
  `MAIL_PROVIDER_CHECK` require `LOCAL_CANONICAL`; `SAFE_TEST` and
  `AUTOMATED_TEST` require `SAFE_TEST`. Mismatches fail and stop. Browser
  entrypoints print purpose, mode, URL, database class and auth mode before
  running. No automatic fallback is allowed. SAFE_TEST UI shows an explicit
  disposable-data badge.
- Reason: A visible, machine-checkable purpose/mode contract prevents an
  owner session or visual acceptance from silently using synthetic data.
- Consequences: Canonical work remains on `http://127.0.0.1:8000`; automated
  work remains on `http://127.0.0.1:18000`. Direct imports, already-running
  unmarked processes, custom browser runners and serverless imports remain
  outside the guarded launcher path and must be treated as unverified.
- Non-goals: Backend business logic, OAuth callback/settings, database schema,
  provider configuration and outgoing-mail behavior were not changed.
- Related task: `TASK-RUNTIME-SELECTION-HARD-GUARD-20260904`.

## DECISION-005 — Irreversible mail actions require an explicit gate

- Decision ID: `DECISION-005`
- Date: `2026-08-30`
- Status: `ACTIVE`
- Context: Real email, SMTP/IMAP, and production data changes are irreversible or externally visible.
- Decision: No real mail action or destructive data operation is allowed without backup, dry-run, validation, and explicit owner approval.
- Reason: Documentation tasks must not turn into unreviewed external actions.
- Consequences: Live mail claims remain `NOT VERIFIED` unless a separately approved acceptance task records evidence.
- Related requirements: project security and destructive-operation rules.
- Related commits: `c076e1be385c3ae6da2716159e1f46fc2fce23d7`.

