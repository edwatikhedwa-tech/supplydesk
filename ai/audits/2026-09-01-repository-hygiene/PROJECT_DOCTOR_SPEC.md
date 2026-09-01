# Future `scripts/doctor.ps1` specification

This is a specification only; no doctor script was created or changed in the
source repository.

## Contract

Default mode is read-only. `-Plan`, `-DryRun` and explicit `-Apply` must be
mutually exclusive. Any future Apply path must use an exact allowlist, create a
manifest/backup first and never operate on `.env*`, databases, migrations,
source, tests or documentation without a separate approved task.

## Checks

- **Git state:** root, branch, HEAD, upstream, staged/modified/untracked/
  ignored FILES, worktree cleanliness; distinguish FILES, PATH ENTRIES and
  DIRECTORIES;
- **dependencies:** Python/Node/npm versions, manifests, `pip check`, clean npm
  lockfile install status;
- **backend health:** entrypoint, bound port, `/`, auth probe, protected API
  response and one unknown-route error;
- **database health:** SQLite journal mode, WAL/SHM presence, read-only
  `integrity_check` and `quick_check`, no migrations or writes;
- **tests:** run configured suite and compare PASS/FAIL/ERROR/SKIP to a stored
  baseline, reporting new failures separately;
- **frontend:** typecheck, lint, production build and bundle output;
- **Playwright:** real local routes, 1440/1024/390 viewports, overflow/a11y,
  screenshots for changed visual areas, no route mocks for acceptance;
- **documentation consistency:** canonical `ai/CURRENT_STATE.md`, links,
  historical markers, duplicate state documents and stale counters;
- **secret hygiene:** names/statuses and high-signal scan without printing
  values; no cookies, tokens, env contents or database rows;
- **worktree hygiene:** generated/cache/vendor distinction, unexpected files,
  lock/PID semantics and snapshot sufficiency.

## Output and exit codes

Write machine-readable JSON plus a human report outside the product tree when
possible. Exit 0 = all required checks pass; 1 = findings or baseline failures;
2 = unavailable/not verified; 3 = safety gate blocked. The output must include
commands, timestamps, versions, limitations and rollback/snapshot paths.
