# Future `PROJECT_MANIFEST.yaml` specification

This is a proposal only; it was not added to the source repository.

```yaml
version: 1
canonical_state_docs:
  - ai/CURRENT_STATE.md
  - ai/ACTIVE_TASK.md
  - ai/DECISIONS.md
  - ai/DEFERRED_FINDINGS.md
runtime_components:
  backend_entrypoint: supplier_app.py
  serverless_entrypoint: api/index.py
  frontend_root: frontend/
  frontend_build: vite
protected_paths:
  - supplier_app.py
  - api/
  - mail/
  - frontend/src/
  - migrations/
  - tests/
  - mail-data/
  - .env*
generated_paths:
  - frontend/dist/
  - frontend/test-results/
  - artifacts/
  - cache/
  - Temp/
test_commands:
  backend: python -m pytest tests -vv --tb=short
  frontend_typecheck: npm run typecheck
  frontend_lint: npm run lint
  frontend_build: npm run build
browser_acceptance:
  base_url: http://127.0.0.1:18000
  real_routes_only: true
  safe_actions_only: true
database:
  type: sqlite
  path: mail-data/supplier.sqlite3
  backup: sqlite_backup_api
  writes_allowed_in_doctor: false
dangerous_operations:
  - send_email
  - smtp_connect
  - migration
  - database_write
  - delete
  - git_push
archive_policy:
  require_manifest: true
  require_canonical_owner: true
  require_three_evidence_points: true
  prefer_quarantine: true
```

The actual manifest must be reconciled with the real runtime before adoption;
the YAML above is not authoritative until tested against source and deployment.
