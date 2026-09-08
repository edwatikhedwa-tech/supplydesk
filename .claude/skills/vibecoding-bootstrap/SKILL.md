---
name: vibecoding-bootstrap
description: Runs the mandatory SupplyDesk VibeCoding session bootstrap (read PROJECT_MANIFEST.yaml, ai/CURRENT_STATE.md, ai/VIBECODING_RULES.md, ai/VIBECODING_TOOL_REGISTRY.yaml in order, extract last_corrected) and the SESSION_WORKSPACE_HARD_GATE. Use at the start of a new session or a new independent task in this repo, before any project analysis, implementation, or state-file update.
---

# VibeCoding bootstrap

This packages the exact sequence CLAUDE.md and `ai/VIBECODING_RULES.md`
already require, so it runs reliably instead of depending on the agent
re-deriving it from a long prose file every session.

## Full bootstrap (new agent session)

1. Run the workspace guard first, before any other project action:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\assert_workspace.ps1
   ```
   A `BLOCKED_WRONG_WORKSPACE` result stops everything else in this list.
2. Read, in this exact order:
   1. `PROJECT_MANIFEST.yaml`
   2. `ai/CURRENT_STATE.md`
   3. `ai/VIBECODING_RULES.md`
   4. `ai/VIBECODING_TOOL_REGISTRY.yaml`
3. Extract `last_corrected` from `ai/VIBECODING_RULES.md`'s frontmatter — this
   is the date used in the mandatory final-response acknowledgement:
   `Я использую правила VibeCoding'a от <last_corrected>.`
4. Also read `ai/LAST_HANDOFF.md`, `ai/DECISIONS.md`, `ai/DEFERRED_FINDINGS.md`,
   `ai/ACTIVE_TASK.md` per CLAUDE.md — check `ai/ACTIVE_TASK.md` for an
   in-progress task before starting new work, to avoid scope conflicts.

## Task Preflight (new independent task, same healthy session)

Skip the full bootstrap; only re-check: workspace guard, current branch,
HEAD, working-tree status (`git status`), active-task/conflict, task
classification and required verification profile. Revalidate the full
bootstrap only if the workspace, Git root, environment, relevant
instructions, or agent context changed since the last full run.

## Acknowledgement

Render exactly once, in the final response of the session, after the task is
completed or stopped — never in intermediate updates:

`Я использую правила VibeCoding'a от <last_corrected>.`

If `ai/VIBECODING_RULES.md` is missing, ambiguous, or its `last_corrected`
date is unreadable, render `VIBECODING POLICY: NOT VERIFIED` exactly once
instead, and do not modify the project.
