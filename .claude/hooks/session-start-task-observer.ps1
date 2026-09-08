[CmdletBinding()]
param()

# Force UTF-8 stdout without a BOM. Windows PowerShell 5.1's default console
# encoding otherwise mangles non-ASCII characters on the way out (observed:
# em-dashes came out as "вЂ”" when this hook's output was captured).
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)

# SessionStart hook: injects the task-observer activation block as
# additionalContext so activation does not depend on skill-description
# matching (tier 1, the least reliable tier per the skill's own docs).
# See CLAUDE.md "## Task-observer activation" for the tier-3 CLAUDE.md
# backup this hook complements.

$workspaceRoot = 'C:\Users\edwat\.claude\projects\C--Users-edwat-SupplyDesk\skill-observations'

$context = @"
Before the first tool call of this session - and before writing or proposing
a plan, not merely before executing one - invoke the task-observer skill AND
execute its Session Start Protocol (storage check, frontmatter scan, review
trigger). Loading the skill and running the protocol are separate steps; a
session that loads the file and stops has activated nothing. Any turn that
will involve a tool call counts; do not classify this session as "too
simple" from its opening message.

The task-observer workspace for this project is:
  $workspaceRoot
Every path the skill uses derives from that root and nothing else. Never
resolve it from the current working directory - a cwd inside a git worktree
under .claude/worktrees/ is torn down and would take a locally-derived log
with it.

After completing each task, check the observation records written this
session and report a one-line summary (ids and titles, or "none logged and
why").
"@

$output = [ordered]@{
    hookSpecificOutput = [ordered]@{
        hookEventName     = 'SessionStart'
        additionalContext = $context
    }
}

$output | ConvertTo-Json -Depth 5 -Compress
exit 0
