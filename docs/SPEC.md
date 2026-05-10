# OpenClaw v3 — Implementation Spec

> Version: 1.0  
> Status: Draft  
> Source: PRD `.pi/plans/openclaw-v3.prd.md`  
> Target: `hitmanbros/openclaw-v3`

---

## 1. System Overview

OpenClaw v3 is a single Matrix bot (`@openclaw`) that runs headless on a VPS. Internally it dispatches subagents through a pipeline modeled on the pi harness. The bot speaks to the owner via Matrix rooms and uses disk-persistent JSON for inter-agent communication.

**Core principle:** One Matrix identity, one sync loop, one process. Subagents are either asyncio tasks (coordinators) or Python subprocesses (workers). All state lives on disk so the bot survives restarts.

---

## 2. Agents

### 2.1 Agent Definitions

| Agent | Type | Model | Thinking | Role | Spawnable? |
|-------|------|-------|----------|------|-----------|
| `nexus` | coordinator | kimi-2.6 | minimal | Main room hub, chat, project spawn, escalation aggregation | no (singleton) |
| `orchestrator` | coordinator | kimi-2.6 | minimal | Per-project pipeline dispatch, ready-set computation, slice tracking | yes (one per project) |
| `scout` | subprocess | kimi-2.6 | minimal | Read-only codebase reconnaissance | yes |
| `planner` | subprocess | kimi-2.6 | medium | PRD + implementation plan creation | yes |
| `slicer` | subprocess | kimi-2.6 | medium | PRD → vertical slices with `blocked_by` | yes |
| `worker` | subprocess | kimi-2.6 | minimal | Code implementation, RED→GREEN test loop | yes |
| `reviewer` | subprocess | kimi-2.6 | minimal | Read-only code review against criteria | yes |
| `tester` | subprocess | kimi-2.6 | minimal | Independent test execution | yes |
| `security-auditor` | subprocess | kimi-2.6 | minimal | Conditional security review | yes |
| `communicator` | subprocess | kimi-2.6 | minimal | User-facing summary drafting | yes |
| `caveman` | subprocess | kimi-2.6 | minimal | Token-saving wrapper for mechanical tasks | yes |

### 2.2 Coordinator vs Subprocess

**Coordinators** (`nexus`, `orchestrator`) run in the main asyncio event loop:
- Access to Matrix client for sending messages
- Access to workspace read/write
- Can spawn subprocess agents
- Can read the filesystem (project configs, workspace state)

**Subprocess agents** (all others) run as isolated Python processes:
- NO access to Matrix client
- NO access to project configs outside their workspace
- Access tools via the tool registry
- Communicate via workspace JSON + inbox JSON
- Workers are **leaves** — they never spawn other agents

### 2.3 Agent Prompt Files

Prompts are stored as markdown files:

```
agents/
├── BASE.md              # Shared base injected into ALL agents
├── nexus.md             # Nexus system prompt
├── orchestrator.md      # Orchestrator system prompt
├── scout.md
├── planner.md
├── slicer.md
├── worker.md
├── reviewer.md
├── tester.md
├── security-auditor.md
├── communicator.md
└── caveman.md
```

Each file uses YAML frontmatter:

```yaml
---
name: worker
description: Implements changes. Writes code, edits files, runs tests.
tools: read, bash, edit, write
model: kimi-2.6
thinking_level: minimal
---
```

The harness constructs the system prompt as:
```
1. YAML frontmatter metadata (not sent to LLM, used for routing)
2. BASE.md content
3. Agent-specific markdown body
4. Room/project context (appended at runtime)
```

---

## 3. Matrix Interface

### 3.1 Bot Identity

- **User ID:** Configurable, default `@openclaw:hoomestead.com`
- **Display Name:** `OpenClaw`
- **Avatar:** Static bot avatar (optional)
- **Device ID:** `openclaw-v3`

### 3.2 Room Types

| Room Type | Purpose | Auto-Join | Created By |
|-----------|---------|-----------|------------|
| **main** | Owner chat, project spawn, status aggregation | yes (config) | owner |
| **ops** | System logs, alerts, status dumps | yes (config) | owner |
| **project** | Per-project pipeline, isolated context | no | nexus |

### 3.3 Room State Events

**Project room state (`com.openclaw.project`):**

```json
{
  "type": "com.openclaw.project",
  "state_key": "",
  "content": {
    "project_id": "alpha-2024-05",
    "name": "Alpha",
    "repo_url": "github.com/owner/repo",
    "fork_url": "github.com/hitmanbros/repo",
    "workspace_path": "/data/projects/!abc123:matrix.org",
    "status": "running",
    "created_at": "2024-05-09T12:00:00Z",
    "owner_id": "@bryan:hoomestead.com"
  }
}
```

### 3.4 Message Types

**Standard events (sent to all rooms):**

| Event Type | Purpose | Room |
|------------|---------|------|
| `m.text` | Plain text fallback | all |
| `m.html` | Rich HTML rendering | all |

**Custom events (sent alongside standard events):**

| Event Type | Direction | Payload |
|------------|-----------|---------|
| `com.openclaw.slice_update` | project room | Slice status change |
| `com.openclaw.status` | project/ops/main | Aggregated status |
| `com.openclaw.dashboard` | ops room | Metrics/structured data |

**Custom event schema:**

```json
{
  "type": "com.openclaw.slice_update",
  "content": {
    "project_id": "alpha-2024-05",
    "slice_id": 3,
    "status": "done",
    "agent": "worker",
    "timestamp": "2024-05-09T12:34:56Z",
    "render_as": "progress_bar",
    "data": {
      "percent": 60,
      "completed_slices": 3,
      "total_slices": 5
    },
    "fallback_html": "<b>Slice 3</b> done by worker (60% complete)"
  }
}
```

### 3.5 Command Reference

**Explicit commands (`!` prefix):**

| Command | Args | Room | Action |
|---------|------|------|--------|
| `!ping` | — | any | Reply "pong" |
| `!plan` | `<repo-url>` or `<project-name>` | main | Create project room, fork, clone |
| `!status` | `[project-name]` | any | Show project status |
| `!approve` | `[slice-id]` | project | Approve HITL gate |
| `!reject` | `[slice-id]` | project | Reject HITL gate |
| `!close` | `<project-name>` | project | Archive project room |
| `!bind` | `<host-path>` | project | Bind-mount host directory |
| `!remember` | `<content>` | any | Store in long-term memory |
| `!recall` | `<query>` | any | Search long-term memory |
| `!help` | — | any | List commands |

**Natural language triggers:**

Nexus detects intent from un-prefixed messages:
- `"build me a login page"` → suggests `!plan` if repo context available
- `"what's the status of Alpha?"` → calls `!status Alpha`
- `"fix the bug in auth.py"` → suggests project-specific fix

---

## 4. Workspace Protocol

### 4.1 File Layout (per project)

```
/data/projects/<room-id>/
├── .pi/
│   ├── workspace.json       # Shared state (system of record)
│   ├── inbox.json           # Point-to-point messages
│   ├── session.json         # Agent status tracking
│   ├── plans/
│   │   └── <slug>.prd.md    # PRD files
│   └── snapshots/
│       └── <slice-id>/      # Pre-worker snapshots
├── src/                     # Cloned repo (fork)
│   └── ...
├── memory.db                # SQLite keyword memory
└── events.jsonl             # Structured log
```

### 4.2 workspace.json Schema

```json
{
  "plan": {
    "prd_path": ".pi/plans/alpha.prd.md",
    "slices": [
      {
        "id": 1,
        "task": "Implement auth middleware",
        "criteria": ["JWT validation works", "401 on missing token"],
        "blocked_by": [],
        "status": "done",
        "agent": "worker",
        "result": "Implemented in src/auth.py",
        "started_at": "2024-05-09T12:00:00Z",
        "completed_at": "2024-05-09T12:15:00Z"
      }
    ]
  },
  "budget": {
    "daily_input_cap": 3000000,
    "hourly_input_cap": 1000000,
    "daily_used": 450000,
    "hourly_used": 120000
  },
  "config": {
    "repo_url": "github.com/owner/repo",
    "fork_url": "github.com/hitmanbros/repo",
    "worker_cap": 3,
    "model": "kimi-2.6"
  }
}
```

### 4.3 inbox.json Schema

```json
{
  "messages": [
    {
      "id": "msg-uuid-1",
      "from": "orchestrator",
      "to": "worker-3",
      "content": "Slice 3 task: implement login handler",
      "timestamp": "2024-05-09T12:00:00Z",
      "read": false
    }
  ]
}
```

### 4.4 session.json Schema

```json
{
  "agents": {
    "orchestrator": {
      "status": "running",
      "pid": 12345,
      "started_at": "2024-05-09T12:00:00Z"
    },
    "worker-3": {
      "status": "running",
      "pid": 12346,
      "started_at": "2024-05-09T12:10:00Z"
    }
  }
}
```

### 4.5 IPC Rules

1. **Workspace is append-only for status fields.** Never delete a key; update in place.
2. **Read workspace ONCE per agent invocation.** Re-read only on explicit retry.
3. **Inbox messages are consumed (read + marked read) not deleted.**
4. **File locking:** Use `fcntl` (POSIX) or atomic renames for concurrent writes.
5. **Polling interval:** Subagents poll workspace every 2s for status changes.

---

## 5. Tool Registry

### 5.1 Tool Definitions

Each tool has a JSON schema for LLM consumption:

```json
{
  "name": "read",
  "description": "Read file contents (text or images). Truncated to 2000 lines / 50KB.",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "File path to read"},
      "offset": {"type": "integer", "description": "Line number to start from"},
      "limit": {"type": "integer", "description": "Max lines to read"}
    },
    "required": ["path"]
  }
}
```

### 5.2 Tool Scoping by Agent

| Tool | Worker | Scout | Reviewer | Orchestrator | Tester |
|------|--------|-------|----------|--------------|--------|
| `read` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `edit` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `write` | ✅ | ❌ | ❌ | ✅ | ❌ |
| `bash` | ✅ | ❌ | ❌ | ❌ | ✅ |
| `grep` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `find` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `ls` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `read_workspace` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `write_workspace` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `read_inbox` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `send_message` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `remember` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `recall` | ✅ | ✅ | ❌ | ❌ | ❌ |
| `subagent` | ❌ | ❌ | ❌ | ✅ | ❌ |

### 5.3 Bash Whitelist

**Allowed commands:**
```
python, python3, pytest, node, npm, cargo, go, make,
git diff, git status, git log, git show, git add, git commit,
cat, echo, grep, find, ls, pwd, wc, head, tail, diff, cmp
```

**Blocked commands (regex patterns):**
```
rm -rf, dd, mkfs, fdisk, iptables, nft, systemctl stop,
userdel, chmod -R, chown -R, sudo, su, eval, exec,
curl, wget, nc, nmap, ssh, scp, sftp, telnet,
git push, git fetch, git pull, git clone,
pip install, npm install, cargo install, go get,
docker, podman, kubectl
```

**Override flow:** Worker requests blocked command → HITL pause → owner approves via `!approve` → command added to per-project override list.

### 5.4 Tool Execution Rules

1. **read:** Never read outside project workspace. Block `~/.ssh`, `~/.aws`, `~/.env`, `**/*secrets*`, `**/*.key`, `**/*.pem`.
2. **bash:** Whitelist check before execution. Timeout default 30s, max 300s.
3. **edit:** `oldText` must match byte-for-byte. Batch multiple edits in one call.
4. **write:** Auto-create parent directories. Never overwrite without read first (except new files).

---

## 6. Pipeline Flow

### 6.1 Full Pipeline

```
Owner: "!plan github.com/me/myapp"
    ↓
Nexus (main room)
    ├── Creates project room
    ├── Forks repo to hitmanbros/myapp
    ├── Clones to /data/projects/<room-id>/
    ├── Sets room state event
    ├── Spawns project orchestrator
    └── Posts: "Project Alpha started in room #alpha"
    ↓
Orchestrator (project room)
    ├── Phase 1: Scout
    │   ├── Spawns scout subprocess
    │   ├── Scout maps src/ → writes report to workspace
    │   └── Posts: "Scout complete. 15 files mapped."
    ├── Phase 2: Planner (HITL gate)
    │   ├── Spawns planner subprocess
    │   ├── Planner reads scout report + goal
    │   ├── Writes PRD to .pi/plans/alpha.prd.md
    │   ├── Posts PRD summary + "Approve with `!approve`"
    │   └── WAITS for owner approval
    ├── Owner: "!approve"
    ├── Phase 3: Slicer
    │   ├── Spawns slicer subprocess
    │   ├── Slicer reads PRD → writes slices to workspace
    │   └── Posts: "5 slices defined. Ready to dispatch."
    ├── Phase 4: Orchestrator dispatch loop
    │   ├── Compute ready-set from blocked_by graph
    │   ├── For each ready slice:
    │   │   ├── Snapshot workspace (cp -a)
    │   │   ├── Spawn worker subprocess
    │   │   ├── Worker edits files, runs tests
    │   │   ├── Worker writes result to workspace
    │   │   ├── Spawn reviewer subprocess
    │   │   ├── Reviewer checks against criteria
    │   │   ├── Spawn tester subprocess
    │   │   ├── Tester runs tests independently
    │   │   ├── If review pass + test pass:
    │   │   │   └── Mark slice done, keep changes
    │   │   ├── If fail:
    │   │   │   ├── Restore from snapshot
    │   │   │   ├── Retry once
    │   │   │   └── If retry fail: mark failed, escalate
    │   │   └── Repeat until all slices done or failed
    ├── Phase 5: Commit
    │   ├── Squash worker commits into one
    │   ├── Push to fork
    │   └── Post PR link
    └── Phase 6: Communicator
        └── Spawns communicator → writes summary to main room
```

### 6.2 HITL Gates

| Gate | Trigger | Action Required | Timeout |
|------|---------|-----------------|---------|
| PRD approval | Planner finishes PRD | Owner `!approve` or `!reject` | 24h |
| Destructive command | Worker requests blocked bash | Owner `!approve <slice>` | 1h |
| Retry failed | Worker failed after retry | Owner decides: skip/fix/restart | 24h |
| Budget exceeded | Pre-project estimate > cap | Owner `!proceed anyway` | 1h |

### 6.3 Escalation Path

```
Worker fails twice
    → Project orchestrator marks failed
    → Posts to project room: "Slice 3 failed, escalating..."
    → Writes to workspace: escalation record
    → Nexus polls workspace (or receives inbox message)
    → Nexus posts to main room: "Alpha slice-3 failed. [details]"
    → Owner sees in main room, replies with instructions
    → Nexus forwards instructions to project orchestrator
    → Project orchestrator acts (skip/retry/restart)
```

### 6.4 Ready-Set Computation

The orchestrator computes the ready-set on every iteration:

```python
def compute_ready_set(slices):
    done = {s.id for s in slices if s.status == 'done'}
    ready = []
    for s in slices:
        if s.status == 'pending' and all(b in done for b in s.blocked_by):
            ready.append(s)
    return ready[:worker_cap]  # respect parallel cap
```

Rules:
- Recompute after every slice completion
- Dispatch entire ready-set in one parallel batch
- Never dispatch more than `worker_cap` simultaneously
- Failed slices block downstream slices indefinitely (unless owner skips)

---

## 7. Memory System

### 7.1 Schema

SQLite table:
```sql
CREATE TABLE memory (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    segment TEXT DEFAULT 'knowledge',  -- 'knowledge', 'decision', 'bug'
    scope TEXT DEFAULT 'project',      -- 'project', 'team', 'user'
    keywords TEXT,                     -- comma-separated for keyword search
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    room_id TEXT                       -- for project scoping
);

CREATE INDEX idx_keywords ON memory(keywords);
CREATE INDEX idx_scope ON memory(scope, room_id);
```

### 7.2 API

- `remember(content, segment='knowledge', scope='project')` → insert row
- `recall(query, limit=5)` → keyword search on `content` + `keywords`, returns top matches

### 7.3 Rules

- Project-scoped memory is isolated per room
- `scope='team'` memories are shared across all projects
- `scope='user'` memories are personal to the owner
- Memory survives bot restart (SQLite on disk)
- No vector embeddings for v3 MVP

---

## 8. Budget System

### 8.1 Counters

Per-project counters in workspace.json:
- `daily_input_cap`: cumulative ceiling per UTC day
- `hourly_input_cap`: rolling 3600s rate limit
- `daily_used`: cumulative today
- `hourly_used`: rolling window

### 8.2 Pre-Project Estimate

Before dispatching workers, orchestrator estimates:
```
estimated_cost = sum(
    slice_count × avg_tokens_per_slice × model_rate
)
```
Nexus presents estimate to owner: "This looks like ~$2.50 in API calls. Proceed?"

### 8.3 Enforcement

1. **Hourly cap exceeded:** Block new worker spawns until window resets.
2. **Daily cap exceeded:** Block all LLM calls for this project until UTC midnight.
3. **Global cap exceeded:** Block ALL projects until owner intervenes.
4. **Pre-project approval:** Owner must confirm estimate before first worker.

---

## 9. Snapshot System

### 9.1 Snapshot Creation

Before each worker:
```bash
rsync -a --delete \
  /data/projects/<room-id>/src/ \
  /data/projects/<room-id>/.pi/snapshots/<slice-id>/
```

Includes:
- `src/` directory (the code)
- `workspace.json` (state at start of slice)

Excludes:
- `.pi/snapshots/` (don't recurse)
- `memory.db` (not code)
- `events.jsonl` (logs)

### 9.2 Restore

On worker failure:
```bash
rsync -a --delete \
  /data/projects/<room-id>/.pi/snapshots/<slice-id>/ \
  /data/projects/<room-id>/src/
```

Restore workspace.json to pre-slice state.

### 9.3 Cleanup

- Keep last 5 snapshots per project
- Auto-delete older snapshots on project close

---

## 10. GitHub Integration

### 10.1 Fork Flow

```
1. Owner: "!plan github.com/owner/myapp"
2. Nexus calls GitHub API: POST /repos/owner/myapp/forks
3. Poll until fork ready (max 60s)
4. Clone fork to /data/projects/<room-id>/src/
5. Set git remote: origin = fork
6. Set upstream: upstream = original
```

### 10.2 Commit Flow

```
1. Worker makes edits in src/
2. Worker runs `git add -A && git commit -m "slice-N: description"`
3. On phase verification:
   a. `git reset --soft <phase-start-commit>`
   b. `git commit -m "phase-X: summary"`
4. `git push origin HEAD`
5. Nexus opens PR: POST /repos/owner/myapp/pulls
```

### 10.3 Repo Registry

Config file maps short names to repos:
```yaml
projects:
  alpha:
    repo: github.com/hitmanbros/my-api
    description: "Main API service"
  claw:
    repo: github.com/hitmanbros/openclaw-v3
    description: "This project"
```

Owner can use `!plan alpha` instead of full URL.

---

## 11. Configuration

### 11.0 Config Philosophy

Configuration must be **easy to change, validate, and persist** without restarting the bot. All tunable parameters should be discoverable and modifiable via Matrix commands. Sensitive values are protected from accidental exposure.

**Design principles:**
- **Two-layer config:** Static (`config.yaml`) for bootstrap values + dynamic (workspace JSON) for runtime overrides.
- **Hot-reload:** Dynamic config changes apply immediately to new agent spawns; existing agents finish with their current values.
- **Validation:** Every config change is validated before application. Invalid values are rejected with an error message.
- **Persistence:** Dynamic changes auto-save to disk within 5 seconds.
- **Discoverability:** `!config` shows all available keys, current values, and default values.
- **Security:** Sensitive keys (`api_key`, `token`, `password`) are masked in output (`ghp_********`).

### 11.1 Static Config (config.yaml)

```yaml
matrix:
  homeserver: "https://matrix.hoomestead.com"
  user_id: "@openclaw:hoomestead.com"
  access_token: "${MATRIX_TOKEN}"  # env var substitution
  device_id: "openclaw-v3"

rooms:
  main: "!main123:hoomestead.com"
  ops: "!ops456:hoomestead.com"

llm:
  provider: "kimi"
  model: "kimi-2.6"
  api_key: "${KIMI_API_KEY}"
  base_url: "https://api.moonshot.cn/v1"

github:
  token: "${GITHUB_TOKEN}"
  username: "hitmanbros"

projects:
  alpha:
    repo: "github.com/hitmanbros/my-api"

defaults:
  worker_cap: 3
  daily_input_cap: 3000000
  hourly_input_cap: 1000000
  max_turns: 50

http:
  port: 8080
  host: "127.0.0.1"
```

### 11.1a Static Config Reload

Static config is read once at startup. To change static values (Matrix creds, API endpoints), restart the bot. These are intentionally stable.

### 11.2 Dynamic Config (workspace.json per project)

Created at project start, mutable at runtime. Dynamic config lives in `workspace.json` under the `config` key and can be changed without restart.

```json
{
  "config": {
    "worker_cap": 3,
    "daily_input_cap": 3000000,
    "hourly_input_cap": 1000000,
    "model": "kimi-2.6",
    "max_turns": 50,
    "bash_timeout": 30,
    "snapshot_keep": 5,
    "pulse_interval_sec": 300,
    "escalation_timeout_sec": 3600,
    "hitl_timeout_sec": 3600,
    "auto_approve_prd": false,
    "commit_message_template": "phase-{phase}: {summary}"
  }
}
```

**Dynamic config keys:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `worker_cap` | int | 3 | Max parallel workers |
| `daily_input_cap` | int | 3000000 | Daily token ceiling |
| `hourly_input_cap` | int | 1000000 | Hourly token ceiling |
| `model` | string | "kimi-2.6" | LLM model for all agents |
| `max_turns` | int | 50 | Max conversation turns per agent |
| `bash_timeout` | int | 30 | Bash command timeout (seconds) |
| `snapshot_keep` | int | 5 | Number of snapshots to retain |
| `pulse_interval_sec` | int | 300 | Log scan interval |
| `escalation_timeout_sec` | int | 3600 | Time before escalating blocked projects |
| `hitl_timeout_sec` | int | 3600 | Time before auto-rejecting HITL gates |
| `auto_approve_prd` | bool | false | Skip PRD approval gate (dangerous) |
| `commit_message_template` | string | "phase-{phase}: {summary}" | Squash commit message template |

### 11.2b Config Commands

| Command | Args | Room | Action |
|---------|------|------|--------|
| `!config` | — | any | Show all config keys, values, defaults |
| `!config get` | `<key>` | any | Show value for one key |
| `!config set` | `<key> <value>` | main/project | Set key to value (validated) |
| `!config reset` | `<key>` | main/project | Reset key to default |
| `!config help` | — | any | Show config key descriptions |

**Examples:**
```
!config set worker_cap 5
!config set daily_input_cap 5000000
!config set bash_timeout 60
!config get worker_cap
!config reset worker_cap
```

### 11.2c Validation Rules

- `worker_cap`: integer, 1–10
- `daily_input_cap`: integer, >= 100000
- `hourly_input_cap`: integer, >= 10000
- `model`: string, must be in allowed models list (`kimi-2.6`, `kimi-2.5`, etc.)
- `bash_timeout`: integer, 5–300
- `snapshot_keep`: integer, 1–20
- `pulse_interval_sec`: integer, 60–3600
- `escalation_timeout_sec`: integer, 300–86400
- `hitl_timeout_sec`: integer, 300–86400
- `auto_approve_prd`: boolean

**Validation flow:**
1. Owner sends `!config set worker_cap 15`
2. Bot validates: 15 > 10 → **rejected**
3. Bot replies: `❌ worker_cap must be between 1 and 10 (got 15)`
4. Owner sends `!config set worker_cap 5`
5. Bot validates: 5 in range → **accepted**
6. Bot replies: `✅ worker_cap set to 5 (was 3)`
7. Bot writes new value to workspace.json
8. Next worker spawn uses cap=5

### 11.2d Scope Hierarchy

Config is resolved in this order (first match wins):

1. **Project room config** (`workspace.json` in project directory)
2. **Main room config** (`workspace.json` in main room directory)
3. **Static config** (`config.yaml` defaults)

Example:
- Static: `worker_cap = 3`
- Main room: `worker_cap = 5`
- Project Alpha: `worker_cap = 2`
- Project Beta: (no override)

Result:
- Alpha uses 2 workers
- Beta uses 5 workers (inherits from main)
- New project uses 5 workers (inherits from main)

### 11.2e Sensitive Key Masking

The following keys are masked in `!config` output:

```python
SENSITIVE_KEYS = {
    "matrix.access_token",
    "llm.api_key",
    "github.token",
    "github.webhook_secret",
}
```

Display: `github.token = ghp_********`

Sensitive keys can only be set via environment variables or by editing `config.yaml` directly (requires restart). They cannot be changed via `!config set`.

### 11.2f Config Persistence

- Dynamic changes are written to `workspace.json` within 5 seconds
- Auto-save on every `!config set`
- Writes use atomic rename (`tmp.json` → `workspace.json`) to prevent corruption
- On startup: read static config → overlay dynamic config → resolve final values

### 11.2g Config Audit Trail

Config changes are logged:
```json
{"timestamp":"2024-05-09T12:34:56Z","event":"config_change","key":"worker_cap","old_value":3,"new_value":5,"changed_by":"@bryan:hoomestead.com","room":"!alpha:matrix.org"}
```

This audit trail is in `events.jsonl` and can be reviewed with `!config log`.

### 11.3 Environment Variables

Required:
- `MATRIX_TOKEN`
- `KIMI_API_KEY`
- `GITHUB_TOKEN`
- `OWNER_MATRIX_ID`

Optional:
- `OPENCLAW_CONFIG_PATH` (default: `./config.yaml`)
- `OPENCLAW_DATA_DIR` (default: `/data/projects`)
- `OPENCLAW_LOG_LEVEL` (default: `INFO`)

---

## 12. Logging

### 12.1 JSON Lines Format

`/var/log/openclaw/events.jsonl`:
```json
{"timestamp":"2024-05-09T12:34:56Z","level":"INFO","project":"alpha","agent":"worker-3","slice":3,"event":"slice_complete","duration_sec":45.2,"tokens_in":1200,"tokens_out":800}
```

Fields:
- `timestamp`: ISO8601 UTC
- `level`: DEBUG/INFO/WARNING/ERROR
- `project`: project ID or "nexus"
- `agent`: agent name or "nexus"
- `slice`: slice number (null for non-slice events)
- `event`: event type (slice_start, slice_complete, slice_fail, hitl_gate, escalation, etc.)
- `duration_sec`: elapsed time (if applicable)
- `tokens_in`: input tokens consumed
- `tokens_out`: output tokens consumed

### 12.2 Matrix Log Routing

| Level | Destination | Format |
|-------|-------------|--------|
| DEBUG | JSON Lines file only | structured |
| INFO | JSON Lines + project room (slice events) | human-readable |
| WARNING | JSON Lines + ops room | human-readable |
| ERROR | JSON Lines + ops room + main room (escalation) | human-readable |

---

## 13. HTTP Status Endpoint

### 13.1 Routes

| Route | Method | Response |
|-------|--------|----------|
| `/health` | GET | `{"status":"ok","uptime_sec":3600}` |
| `/status` | GET | `{"projects":[{"id":"alpha","status":"running","slices_done":3,"slices_total":5}],"agents_active":4}` |
| `/metrics` | GET | Prometheus-style text (future) |

### 13.2 Binding

- Bind to `127.0.0.1` by default (localhost only)
- No auth required (firewalled)
- Runs in same asyncio loop as Matrix client

---

## 14. Deployment

### 14.1 Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "-m", "openclaw"]
```

### 14.2 docker-compose.yml (local dev)

```yaml
version: "3.8"
services:
  openclaw:
    build: .
    env_file: .env
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - openclaw-data:/data/projects
      - openclaw-logs:/var/log/openclaw
    ports:
      - "127.0.0.1:8080:8080"
    restart: unless-stopped

volumes:
  openclaw-data:
  openclaw-logs:
```

### 14.3 systemd Service

```ini
[Unit]
Description=OpenClaw v3
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
RestartSec=5
EnvironmentFile=/etc/openclaw/.env
ExecStart=/usr/bin/docker run --rm \
  --name openclaw-v3 \
  --env-file /etc/openclaw/.env \
  -v /data/openclaw:/data/projects \
  -v /var/log/openclaw:/var/log/openclaw \
  -p 127.0.0.1:8080:8080 \
  openclaw:v3
ExecStop=/usr/bin/docker stop openclaw-v3

[Install]
WantedBy=multi-user.target
```

---

## 15. Security Model

### 15.1 Isolation Layers

1. **Process isolation:** Workers are subprocesses with their own PID
2. **Filesystem isolation:** Workers only access `/data/projects/<room-id>/src/`
3. **Network isolation:** Workers have no network access (future: network namespace)
4. **Tool sandbox:** Bash whitelist blocks dangerous commands
5. **Snapshot rollback:** Pre-worker snapshots enable recovery from corruption

### 15.2 Secret Handling

- API keys in environment variables only
- `.env` files on local dev and VPS (not in git)
- Workers never see Matrix token, GitHub token, or API keys
- LLM API key is injected into worker env, but workers cannot read it from disk

### 15.3 Access Control

- Solo owner model
- Only owner can start projects, approve HITL, or bind host directories
- Room membership = access (invite-only rooms)

---

## 16. Pulse Monitor

### 16.1 Behavior

- Not a subagent
- `asyncio.Task` running in main process
- Every 5 minutes: reads last N lines of service logs
- Deduplicates errors by SHA1 fingerprint
- Posts new errors to ops room

### 16.2 Self-Protection

- Filter out `[pulse]` log lines (avoid feedback loop)
- Skip if same fingerprint seen in last hour
- No delegation, no escalation, no loops

---

## 17. File System Layout (repo)

```
openclaw-v3/
├── openclaw/                    # Main Python package
│   ├── __init__.py
│   ├── __main__.py              # Entry point: python -m openclaw
│   ├── bot.py                   # Matrix client, message loop
│   ├── nexus.py                 # Nexus orchestrator (main room)
│   ├── project_orchestrator.py  # Per-project pipeline
│   ├── subagent/                # Subagent runner
│   │   ├── __init__.py
│   │   ├── runner.py            # Spawn subprocess agents
│   │   ├── workspace.py         # read_workspace / write_workspace
│   │   ├── inbox.py             # send_message / read_inbox
│   │   └── snapshot.py          # Pre-worker snapshot / restore
│   ├── tools/                   # Tool implementations
│   │   ├── __init__.py
│   │   ├── registry.py          # ToolRegistry, scoping
│   │   ├── fs.py                # read, edit, write
│   │   ├── bash.py              # bash execution + whitelist
│   │   ├── search.py            # grep, find, ls
│   │   ├── memory.py            # remember, recall
│   │   └── github.py            # fork, clone, commit, PR
│   ├── llm/                     # LLM client
│   │   ├── __init__.py
│   │   ├── client.py            # Kimi API wrapper
│   │   └── prompt.py            # Prompt construction (BASE.md + agent + context)
│   ├── matrix/                  # Matrix client wrapper
│   │   ├── __init__.py
│   │   ├── client.py            # nio wrapper
│   │   ├── events.py            # Custom event types
│   │   └── commands.py          # Command parser (!plan, !status, etc.)
│   ├── config/                  # Configuration
│   │   ├── __init__.py
│   │   ├── loader.py            # config.yaml parsing
│   │   └── defaults.py          # Default values
│   ├── memory/                  # SQLite memory
│   │   ├── __init__.py
│   │   └── store.py             # Keyword search DB
│   ├── budget/                  # Cost tracking
│   │   ├── __init__.py
│   │   └── gate.py              # Cap enforcement
│   ├── http/                    # Status endpoint
│   │   ├── __init__.py
│   │   └── server.py            # aiohttp / httpx server
│   └── logging/                 # Structured logging
│       ├── __init__.py
│       └── jsonl.py             # JSON Lines writer
├── agents/                      # Agent system prompts
│   ├── BASE.md
│   ├── nexus.md
│   ├── orchestrator.md
│   ├── scout.md
│   ├── planner.md
│   ├── slicer.md
│   ├── worker.md
│   ├── reviewer.md
│   ├── tester.md
│   ├── security-auditor.md
│   ├── communicator.md
│   └── caveman.md
├── tests/                       # pytest tests
│   ├── test_nexus.py
│   ├── test_orchestrator.py
│   ├── test_workspace_ipc.py
│   ├── test_snapshot.py
│   ├── test_tool_registry.py
│   ├── test_bash_whitelist.py
│   ├── test_budget_gate.py
│   └── test_matrix_commands.py
├── docs/
│   ├── SPEC.md                  # This file
│   ├── EVENTS.md                # Custom event schema registry
│   ├── ARCHITECTURE.md          # High-level design
│   └── ADR/                     # Architecture Decision Records
├── scripts/
│   ├── setup.sh                 # First-time setup
│   └── deploy.sh                # VPS deployment
├── config.yaml.example
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 18. Error Handling

### 18.1 Worker Failure

1. Catch exception or timeout
2. Restore from snapshot
3. Retry once with same instructions
4. If retry fails:
   - Mark slice `failed`
   - Write error details to workspace
   - Notify project orchestrator
   - Orchestrator posts to project room
   - Escalate to Nexus (if serious) → main room

### 18.2 Matrix Connection Loss

1. Exponential backoff reconnect (1s, 2s, 4s, 8s, max 60s)
2. On reconnect: resume sync from last token
3. Active projects continue (they don't depend on Matrix)
4. Log reconnect events

### 18.3 LLM API Failure

1. Retry once with same prompt (transient errors)
2. If persistent: mark agent as failed, surface error
3. Do not infinite retry (cost control)

---

## 19. Testing Strategy

### 19.1 Unit Tests

| Module | Test Coverage |
|--------|--------------|
| `workspace.py` | Concurrent read/write, atomicity, schema validation |
| `snapshot.py` | Snapshot creation, restore, cleanup |
| `tool_registry.py` | Agent scoping, tool lookup, schema generation |
| `bash.py` | Whitelist enforcement, timeout, output capture |
| `budget_gate.py` | Cap enforcement, window reset, global ceiling |
| `commands.py` | Command parsing, intent detection, arg extraction |
| `jsonl.py` | Log format, rotation, field completeness |

### 19.2 Integration Tests

| Flow | Test |
|------|------|
| `!plan` | Room created, forked, cloned, state set |
| Scout→Planner | Scout report → planner PRD → HITL pause |
| Slicer→Orchestrator | PRD → slices → ready-set computation |
| Worker→Reviewer→Tester | File edit → review pass → test pass |
| Snapshot→Restore | Edit → snapshot → corrupt → restore → verify |
| Escalation | Worker fail → retry fail → Nexus → main room |

### 19.3 Test Principles

- Test external behavior, not internal state
- Use temporary directories for filesystem tests
- Mock LLM API (don't call real API in tests)
- Mock Matrix API for command tests
- Each test is independent (no shared state)

---

## 20. Versioning & Compatibility

- **v3.0.0:** MVP with all 15 slices
- Custom event types versioned: `com.openclaw.v1.slice_update`
- Workspace schema versioned: `"schema_version": "1.0"` in workspace.json
- Future schema changes must include migration path

---

## 21. Open Questions

1. Should workers have network access for package managers (pip, npm) or should all dependencies be pre-installed in the Docker image?
2. How should the bot handle private GitHub repos? (SSH key vs token with repo scope)
3. Should the dashboard HTTP endpoint support WebSocket for real-time updates?
4. What's the maximum project room count before performance degrades?
5. Should failed slices be auto-skipped after N hours of owner inactivity?
