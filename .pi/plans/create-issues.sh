#!/bin/bash
set -e

REPO="hitmanbros/openclaw-v3"
LABEL="needs-triage"

declare -a TITLES=(
  "Matrix Bot MVP"
  "Project Room Lifecycle"
  "Subagent IPC + Worker Runner"
  "Tool Registry + Agent Scoping"
  "Scout → Planner Pipeline"
  "Slicer + Orchestrator Dispatch"
  "Real Worker + Reviewer + Tester"
  "GitHub Commit Workflow"
  "HITL + Escalation"
  "Budget Gate"
  "Memory System"
  "Ops Room + Structured Logging"
  "Custom Matrix Events"
  "Pulse Monitor"
  "Deployment"
)

declare -a BODIES=(
'## What to build
Single `@openclaw` Matrix bot connects to homeserver, joins main room, and replies to `!ping` and casual chat. Nexus identity is established. No subagents yet — just the bot core, Matrix client, and basic command parsing.

## Acceptance criteria
- [ ] Bot connects to Matrix with nio asyncio client
- [ ] Responds to `!ping` in main room
- [ ] Answers casual chat via LLM (Nexus persona)
- [ ] Parses `!` prefix commands and natural language intent
- [ ] Posts to ops room on startup
- [ ] Tests: Matrix event parsing, command detection, message sending'

'## What to build
`!plan <repo>` command creates a new Matrix project room, auto-invites owner, forks the GitHub repo to owner account, clones to isolated workspace `/data/projects/<room-id>/`. Sets `com.openclaw.project` state event. No pipeline execution yet.

## Acceptance criteria
- [ ] `!plan github.com/owner/repo` creates room + fork + clone
- [ ] Room gets `com.openclaw.project` state with name/repo/status
- [ ] Isolated workspace directory created and populated from fork
- [ ] Owner auto-invited to project room
- [ ] Tests: room creation, fork API call, clone verification'
'Blocked by #ISSUE_1'

'## What to build
Spawn Python subprocess workers. Implement disk workspace JSON read/write (`read_workspace`/`write_workspace`) and inbox JSON messaging (`send_message`/`read_inbox`). File-copy snapshot before worker start, restore on failure. Test with a worker that writes a file.

## Acceptance criteria
- [ ] Worker spawned as Python subprocess with env/config
- [ ] Worker reads task from workspace, writes result back
- [ ] Inbox messages delivered between agents
- [ ] Pre-worker snapshot via `cp -a` or `rsync`
- [ ] Restore from snapshot on worker failure
- [ ] Tests: workspace round-trip, inbox delivery, snapshot/restore'
'Blocked by #ISSUE_2'

'## What to build
Port v2 tool registry. Each agent type gets a scoped subset: worker (`read`, `bash`, `edit`, `write`), scout (`read`, `grep`, `find`, `ls`), reviewer (`read`, `grep`, `find`, `ls`), orchestrator (`read`, `write_workspace`, `read_workspace`). Bash whitelist enforced. Worker uses tools via registry.

## Acceptance criteria
- [ ] Tool registry maps agent type → allowed tools
- [ ] Bash whitelist: python, pytest, node, npm test, cargo test, go test, make, git diff, git status
- [ ] Blocked commands rejected: rm -rf, curl, wget, sudo, ssh, etc.
- [ ] Tool schemas exposed to LLM correctly per agent
- [ ] Tests: tool scoping, bash whitelist enforcement'
'Blocked by #ISSUE_3'

'## What to build
End-to-end planning pipeline: scout reconnaissance (maps codebase) → planner produces PRD. HITL gate pauses before proceeding — owner must approve PRD in project room. No code execution in this slice.

## Acceptance criteria
- [ ] Scout runs in subprocess, maps project files, writes report to workspace
- [ ] Planner reads scout report, writes PRD to `.pi/plans/`
- [ ] Orchestrator pauses after PRD, posts "Approve with `!approve`"
- [ ] Owner `!approve` continues pipeline
- [ ] Tests: scout→planner handoff, HITL pause/resume'
'Blocked by #ISSUE_4'

'## What to build
PRD → slicer breaks into vertical slices with explicit `blocked_by` dependencies → orchestrator computes ready-set from DAG and dispatches parallel test workers (using trivial echo/write tasks to verify dispatch logic).

## Acceptance criteria
- [ ] Slicer reads PRD, writes slices array to workspace
- [ ] Orchestrator computes ready-set from `blocked_by` graph
- [ ] Dispatches entire ready-set in parallel (respect cap)
- [ ] Tracks slice status: pending/running/done/failed/blocked
- [ ] Tests: DAG ready-set computation, parallel dispatch, status tracking'
'Blocked by #ISSUE_5'

'## What to build
Real code-change pipeline: worker makes actual file edits, reviewer verifies against slice criteria and PRD acceptance criteria, tester runs tests independently. First end-to-end code change with all three agents.

## Acceptance criteria
- [ ] Worker reads slice task, edits files, runs tests RED→GREEN
- [ ] Reviewer reads changes, checks against criteria, writes findings
- [ ] Tester runs tests independently, reports pass/fail
- [ ] Orchestrator gates: review pass + test pass = slice done
- [ ] Tests: worker edit verification, reviewer correctness, tester independence'
'Blocked by #ISSUE_6'

'## What to build
Phase verification triggers squash commit of all worker local commits into one clean commit, pushes to project fork. Nexus can open PR to original repo. End-to-end: code edit → verify → commit → push → PR.

## Acceptance criteria
- [ ] Orchestrator squashes worker commits on phase verify
- [ ] Pushes clean commit to fork
- [ ] Nexus posts PR link to project room
- [ ] Tests: squash logic, push verification, PR creation'
'Blocked by #ISSUE_7'

'## What to build
Destructive operations (bash commands outside whitelist, file deletions, etc.) pause for owner approval in project room. Blocked projects or repeated worker failures escalate to Nexus, which surfaces in main room. Test with simulated `rm` / `curl`.

## Acceptance criteria
- [ ] Worker destructive command triggers HITL pause
- [ ] Owner approves with `!approve <slice>` or rejects
- [ ] Retry failure escalates to project room → Nexus → main room
- [ ] Tests: HITL trigger, approval flow, escalation chain'
'Blocked by #ISSUE_7'

'## What to build
Per-project daily/hourly token caps, pre-project cost estimate + owner approval, global hard ceiling. Test by simulating cap exceed.

## Acceptance criteria
- [ ] Daily/hourly token counters per project room
- [ ] Pre-project estimate shown to owner before workers start
- [ ] Global ceiling blocks all dispatch when exceeded
- [ ] Tests: cap enforcement, estimate accuracy, global ceiling'
'Blocked by #ISSUE_3'

'## What to build
SQLite keyword-search memory per project. `remember(content, scope='project')` and `recall(query)` tools. Persists across project sessions and bot restarts.

## Acceptance criteria
- [ ] SQLite DB per project at `/data/projects/<id>/memory.db`
- [ ] `remember` inserts with timestamp and keywords
- [ ] `recall` returns matching entries by keyword search
- [ ] Memory survives bot restart
- [ ] Tests: remember/recall round-trip, persistence, keyword matching'
'Blocked by #ISSUE_3'

'## What to build
Ops room receives system logs and status dumps. Structured JSON Lines log file at `/var/log/openclaw/events.jsonl`. HTTP `/health` and `/status` endpoints for monitoring.

## Acceptance criteria
- [ ] Ops room created/referenced on startup
- [ ] Critical errors posted to ops room
- [ ] JSON Lines file with one object per event
- [ ] `/health` returns OK, `/status` returns project summaries
- [ ] Tests: log file format, endpoint responses, ops room delivery'
'Blocked by #ISSUE_1'

'## What to build
Bot sends custom Matrix event types: `com.openclaw.slice_update`, `com.openclaw.status`, `com.openclaw.dashboard`. Each carries structured data + `render_as` hint + `fallback_html`. Desktop client renders rich HTML; mobile-ready structure.

## Acceptance criteria
- [ ] Custom events sent alongside `m.text`/`m.html`
- [ ] Event schema: `type`, `data`, `render_as`, `fallback_html`
- [ ] hoomestead-chat renders `render_as` widgets
- [ ] Unknown clients show `fallback_html`
- [ ] Tests: event structure, client rendering'
'Blocked by #ISSUE_6'

'## What to build
Scheduled cron/task (not a subagent) scans service logs for errors, posts alerts to ops room. Uses v2 Pulse logic but simplified — no delegation, no Matrix envelopes.

## Acceptance criteria
- [ ] Asyncio task or cron job runs every N minutes
- [ ] Tails logs, filters for errors/new patterns
- [ ] Deduplicates by fingerprint
- [ ] Posts alert to ops room with context
- [ ] Tests: log scanning, dedup, alert formatting'
'Blocked by #ISSUE_12'

'## What to build
Dockerfile, systemd service unit, docker-compose for local dev, `.env` template. Single container image, auto-restart via systemd, same image locally and on VPS.

## Acceptance criteria
- [ ] Dockerfile builds clean image
- [ ] docker-compose for local dev with volume mounts
- [ ] systemd service unit with auto-restart
- [ ] `.env.example` with all required vars
- [ ] Tests: image build, service start/stop'
'Blocked by #ISSUE_12'
)

declare -a TYPES=(
  "AFK" "AFK" "AFK" "AFK" "HITL" "AFK" "AFK" "AFK" "HITL" "AFK" "AFK" "AFK" "AFK" "AFK" "AFK"
)

# Create issues sequentially and collect numbers
declare -a ISSUE_NUMS

for i in "${!TITLES[@]}"; do
  idx=$((i + 1))
  title="${TITLES[$i]}"
  body="${BODIES[$i]}"
  type="${TYPES[$i]}"
  
  # Replace placeholder issue numbers with real ones
  for j in "${!ISSUE_NUMS[@]}"; do
    ref_idx=$((j + 1))
    body="${body//\#ISSUE_$ref_idx/${ISSUE_NUMS[$j]}}"
  done
  
  # Add type label
  labels="$LABEL,$type"
  
  echo "Creating issue $idx: $title"
  num=$(gh issue create --repo "$REPO" --title "$title" --body "$body" --label "$labels" | grep -oP '/issues/\K\d+')
  ISSUE_NUMS+=("#$num")
  echo "  -> $num"
done

echo ""
echo "All issues created:"
for i in "${!ISSUE_NUMS[@]}"; do
  echo "  $((i+1)). ${ISSUE_NUMS[$i]} ${TITLES[$i]}"
done
