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

