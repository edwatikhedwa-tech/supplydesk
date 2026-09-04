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

