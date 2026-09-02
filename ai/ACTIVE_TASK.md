---
document_id: TASK-LOCK-005
status: CURRENT
canonical: false
owner: project-control
updated_at: 2026-09-02
based_on_commit: f969b769a43b41849c8e996de856ebf85a344a46
---

# Active Task

Task ID: `NONE`
Agent: `Codex`
Mode: `CLOSE`
Started: `2026-09-02`
Scope: `controlled content-level review of Finding-009 allowlisted retained files`
Allowed files: `ai/**`; no product/data/runtime/legacy changes
Status: `IDLE — controlled review complete; Finding-009 is SECURITY_REVIEW_REQUIRED`
Last update: `2026-09-02`

## Цель

Проверить содержимое только allowlisted retained files локально, не выводя и
не сохраняя секретные значения, и определить окончательный статус
`FINDING-009`.

## Границы

Product behavior, frontend UI, API, database schema/data, migrations, mail
data, secret values, quarantine, legacy checkout, dependencies, governance
policy, Workspace Guard behavior and CI architecture are not changed. Candidate
files are read only in memory for classification; values are not output,
copied, saved, deleted or rotated. Backend, frontend, CI and Playwright are not
run.

## Acceptance

The previous filename-level evidence is reused; only the exact allowlist is
read for content classification; Git exposure is separated from local archive
retention; Finding-009 receives an evidence-backed status; product code is
unchanged.

## Следующий шаг

Owner approval is required before any retained secret-bearing copy is deleted
or credentials are rotated; no Git history rewrite is authorized by this task.

