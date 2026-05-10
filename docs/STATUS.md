# OpenClaw v3 — Project Status

> Last updated: 2026-05-10
> Repo: https://github.com/hitmanbros/openclaw-v3
> Tests: **209 passing**
> Bot: `@openclaw:hoomestead.com` (live on VPS)

---

## Architecture Overview

OpenClaw v3 is a **single Matrix bot** with an internal subagent pipeline. Unlike v2's 7-bot architecture, v3 uses one Matrix identity (`@openclaw:hoomestead.com`) that dispatches ephemeral subprocess agents via disk-persistent IPC.

```
Owner (Matrix)
    │
    ▼
┌─────────────────────────────────────────────┐
│  @openclaw:hoomestead.com (single bot)     │
│  ┌─────────┐                                │
│  │  Nexus  │ ← main room hub, chat, spawn   │
│  └────┬────┘                                │
│       │                                     │
│       │ !plan github.com/owner/repo         │
│       ▼                                     │
│  ┌──────────────┐  ┌──────────────────┐     │
│  │ Project Room │  │ Project Room     │     │
│  │ (Room 1)     │  │ (Room 2)         │     │
│  └──────┬───────┘  └────────┬─────────┘     │
│         │                    │               │
│  ┌──────▼────────────────────▼───────┐      │
│  │     Orchestrator (per project)    │      │
│  │  Computes ready-sets from graph   │      │
│  │  Spawns workers as subprocesses   │      │
│  └───────────────────────────────────┘      │
│                                             │
│  IPC: workspace JSON + inbox JSON (disk)    │
│  LLM: Kimi k2.6 via Moonshot API            │
└─────────────────────────────────────────────┘
```

---

## ✅ DONE

### Core Infrastructure

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| Matrix client | `openclaw/matrix/client.py` | ✅ Live | `nio.AsyncClient`, callbacks, auto-join, presence |
| Command parser | `openclaw/matrix/commands.py` | ✅ | `!ping`, `!plan`, `!status`, `!config get/set` |
| Custom events | `openclaw/matrix/events.py` | ✅ | HTML rendering, `com.openclaw.*` events |
| Config loader | `openclaw/config/validation.py` | ✅ | Env substitution, YAML validation |
| LLM client | `openclaw/llm/client.py` | ✅ | Kimi k2.6, base URL `.ai`, **no temperature** |
| Prompt loader | `openclaw/llm/prompts.py` | ✅ | BASE.md + agent.md injection, room context |
| HTTP server | `openclaw/http/server.py` | ✅ | `/health`, `/status` on port 8080 |
| Budget gate | `openclaw/budget/` | ✅ | Daily/hourly caps, token tracking |
| Memory store | `openclaw/memory/` | ✅ | SQLite keyword search |
| Pulse monitor | `openclaw/pulse/` | ✅ | Health checks, alerts |

### Agent System

| Agent | Prompt | Subprocess Entry | Status |
|-------|--------|-----------------|--------|
| `nexus` | `agents/nexus.md` | `__main__.py` route | ✅ **Live** with identity lock |
| `scout` | `agents/scout.md` | `__main__.py` route | ✅ Code exists |
| `planner` | `agents/planner.md` | `__main__.py` route | ✅ Code exists |
| `slicer` | `agents/slicer.md` | `__main__.py` route | ✅ Code exists |
| `orchestrator` | `agents/orchestrator.md` | `__main__.py` route | ✅ Code exists |
| `worker` | `agents/worker.md` | `__main__.py` route | ✅ Code exists |
| `reviewer` | `agents/reviewer.md` | `__main__.py` route | ✅ Code exists |
| `tester` | `agents/tester.md` | `__main__.py` route | ✅ Code exists |
| `communicator` | `agents/communicator.md` | `__main__.py` route | ✅ Code exists |
| `security-auditor` | `agents/security-auditor.md` | `__main__.py` route | ✅ Code exists |
| `caveman` | `agents/caveman.md` | `__main__.py` route | ✅ Code exists |
| `BASE.md` | `agents/BASE.md` | — | ✅ Injected into all prompts |

### Project Management

| Feature | File | Status |
|---------|------|--------|
| Room lifecycle | `openclaw/project.py` | ✅ Create, invite, archive |
| GitHub fork | `openclaw/project.py` | ✅ Forks to owner account |
| Git clone | `openclaw/project.py` | ✅ Clones fork to workspace/src/ |
| Upstream remote | `openclaw/project.py` | ✅ Sets upstream to original |
| Subagent runner | `openclaw/subagent/runner.py` | ✅ Spawns any agent type |
| Workspace IPC | `.pi/workspace.json` | ✅ Read/write/persist |
| Inbox IPC | `.pi/inbox.json` | ✅ Send/read/clear |

### Tool Registry

| Tool | Implementation | Status |
|------|---------------|--------|
| `read` | File read with limits | ✅ |
| `write` | File create/overwrite | ✅ |
| `edit` | Exact text replacement | ✅ |
| `bash` | Whitelist + timeout | ✅ |
| `grep` | Content search | ✅ |
| `find` | File glob search | ✅ |
| `ls` | Directory listing | ✅ |

### Deployment

| Component | Status |
|-----------|--------|
| Dockerfile | ✅ Multi-stage, non-root, read-only |
| docker-compose | ✅ Port 8080, volume mounts |
| systemd service | ✅ `openclaw-v3.service` on VPS |
| VPS user | ✅ `openclaw-v3` (uid 1002) |
| v2 stopped | ✅ Service disabled |
| v1 stopped | ✅ Service disabled |
| Read-only container | ✅ `--read-only --tmpfs /tmp` |
| Port mapping | ✅ `127.0.0.1:8081→8080` |

### Tests

**209 tests passing** across:
- `test_matrix_client.py` — Matrix sync, callbacks
- `test_commands.py` — Command parsing
- `test_config_loader.py` — Config validation
- `test_llm_client.py` — LLM chat completions
- `test_budget_gate.py` — Token caps
- `test_memory.py` — SQLite search
- `test_pulse.py` — Health checks
- `test_subagent_ipc.py` — Workspace/inbox
- `test_tool_registry.py` — Tool dispatch
- `test_real_tools.py` — Tool implementations
- `test_project_room.py` — Room lifecycle
- `test_github_commit.py` — Git operations
- `test_github_workflow.py` — Fork/clone/upstream
- `test_prompt_loader.py` — Prompt injection
- `test_worker_reviewer_tester.py` — Agent stubs
- `test_scout_planner.py` — Pipeline stubs
- `test_slicer_dispatch.py` — Dispatch stubs
- `test_integration.py` — End-to-end
- `test_hitl_escalation.py` — HITL gates
- `test_deployment.py` — Docker/systemd config
- `test_ops_room.py` — Ops room messages
- `test_main.py` — Bot entry point

---

## 🚧 PARTIALLY DONE

### Agent Subprocess Loop

**Status:** Entry point exists, **tool loop is stubbed**.

**File:** `openclaw/agents/__main__.py`

**Current:** Each agent has a stub that prints "Running {name}" and exits.
**Missing:** Real tool loop that reads workspace, uses tools, writes results iteratively.

**What needs to happen:**
1. Agent subprocess starts with `OPENCLAW_AGENT_NAME` and `OPENCLAW_WORKSPACE`
2. Reads workspace for task description
3. Builds messages with system prompt + task
4. Calls LLM with tool schemas
5. Parses tool calls from response
6. Executes tools, writes results back
7. Repeats until LLM returns final answer
8. Writes result to workspace

### HITL Gates

**Status:** Code exists, **not wired to pipeline**.

**File:** `openclaw/hitl/` (if exists) or inline in nexus/orchestrator

**Current:** Concept of HITL (Human-In-The-Loop) is documented.
**Missing:** Actual pause mechanism after planner produces PRD, before destructive ops.

### Config Persistence

**Status:** `!config get/set` commands exist, **don't persist**.

**File:** `openclaw/nexus.py`

**Current:** Prints "not yet persisted" for set operations.
**Missing:** Atomic write to workspace JSON with validation.

---

## ❌ NOT YET IMPLEMENTED

### 1. End-to-End Pipeline

**The big one.** `!plan` currently:
- ✅ Creates project room
- ✅ Forks repo
- ✅ Clones to workspace/src/
- ❌ Does NOT spawn scout
- ❌ Does NOT spawn planner
- ❌ Does NOT spawn slicer
- ❌ Does NOT dispatch workers
- ❌ Does NOT run reviewer/tester
- ❌ Does NOT commit/push/PR

**Flow that needs wiring:**
```
!plan github.com/owner/repo
  → Nexus creates project room
  → Nexus delegates to Orchestrator in project room
  → Orchestrator spawns Scout (subprocess)
    → Scout writes scout report to workspace
  → Orchestrator spawns Planner (subprocess)
    → Planner reads scout report
    → Planner writes PRD to workspace
    → HITL: pause, ask owner to approve PRD
  → Orchestrator spawns Slicer (subprocess)
    → Slicer reads PRD
    → Slicer writes slices to workspace
  → Orchestrator computes ready-set from blocked_by graph
  → For each ready slice:
    → Spawns Worker (subprocess) with slice task
    → Worker uses tools (read/edit/write/bash) to edit code
    → Worker writes result to workspace
    → Spawns Reviewer (subprocess) to review code
    → Spawns Tester (subprocess) to run tests
  → If all slices pass:
    → Git squash commit
    → Push to fork
    → Open PR to original repo
  → If any slice fails twice:
    → Escalate to Nexus in main room
```

### 2. Git Commit/PR Workflow

**File:** `openclaw/github/`

**Current:** Fork and clone work.
**Missing:**
- Squash commit on phase verify
- Push to fork
- Open PR to original repo via GitHub API
- Handle merge conflicts

### 3. Live Tool Loop in Workers

**File:** `openclaw/agents/__main__.py` or new `openclaw/agents/loop.py`

**Missing:**
- Tool call parsing from LLM response (Kimi supports function calling)
- Tool execution dispatch
- Result formatting back to LLM
- Iteration until completion
- Timeout handling

### 4. Escalation Manager

**Missing:**
- Cross-room message routing (project room → main room)
- Escalation thresholds (budget cap, repeated failures)
- Owner notification format

### 5. Multi-Project Coordination

**Missing:**
- `!close <name>` command (archive project room)
- Cross-project resource limits (total workers across all projects)
- Shared budget pool

### 6. Security Hardening

**Missing:**
- `security-auditor` agent actually runs on auth/secret changes
- Supply chain audit on new dependencies
- Input sanitization on bash commands (whitelist is basic)
- File traversal prevention outside workspace

### 7. Memory / Context

**Missing:**
- Long-term memory across sessions (currently in-memory only)
- Project-specific context injection
- Conversation summarization for long projects

### 8. Testing

**Missing:**
- Integration tests for full pipeline (scout→planner→slicer→worker)
- Live Matrix tests (currently all mocked)
- Live GitHub API tests (currently all mocked)
- Load tests for concurrent workers

---

## Next Steps (Priority Order)

### Phase 1: Tool Loop (Critical)

1. **Implement agent tool loop**
   - Parse tool calls from Kimi response
   - Dispatch to tool registry
   - Write results back
   - Iterate until done
   - File: `openclaw/agents/loop.py`

2. **Wire `__main__.py` to use loop**
   - Scout: reads workspace, maps codebase, writes report
   - Planner: reads report, writes PRD
   - Worker: reads slice, uses tools, edits code

### Phase 2: Pipeline (Critical)

3. **Orchestrator dispatch**
   - Read PRD and slices from workspace
   - Compute ready-set from `blocked_by`
   - Spawn workers in parallel (max 10)
   - Track status

4. **HITL integration**
   - Pause after planner PRD
   - Ask owner for approval in project room
   - Resume on `!approve` or `!reject`

### Phase 3: Git Workflow (High)

5. **Commit/PR automation**
   - Git squash on verify
   - Push to fork
   - Open PR via GitHub API

### Phase 4: Polish (Medium)

6. **Config persistence**
   - Atomic workspace writes
   - Validation

7. **Escalation manager**
   - Cross-room routing
   - Thresholds

8. **Integration tests**
   - End-to-end pipeline test
   - Live smoke tests

---

## Key Files Reference

| Purpose | Path |
|---------|------|
| Bot entry | `openclaw/__main__.py` |
| Bot main loop | `openclaw/main.py` |
| Nexus orchestrator | `openclaw/nexus.py` |
| Project manager | `openclaw/project.py` |
| Subagent runner | `openclaw/subagent/runner.py` |
| Agent subprocess entry | `openclaw/agents/__main__.py` |
| LLM client | `openclaw/llm/client.py` |
| Prompt loader | `openclaw/llm/prompts.py` |
| Matrix client | `openclaw/matrix/client.py` |
| Command parser | `openclaw/matrix/commands.py` |
| Tool registry | `openclaw/tools/` |
| Agent prompts | `agents/*.md` |
| Tests | `tests/*.py` |
| Config | `config.yaml` |
| PRD | `.pi/plans/openclaw-v3.prd.md` |
| Spec | `docs/SPEC.md` |
| This status | `docs/STATUS.md` |

---

## Environment

| Variable | Value |
|----------|-------|
| Homeserver | `https://matrix.hoomestead.com` |
| Bot MXID | `@openclaw:hoomestead.com` |
| Main room | `!GGnkLXZSGwvdXdlnFO:hoomestead.com` |
| Ops room | `!gknPfBvJqpjLoInuIl:hoomestead.com` |
| LLM | Kimi k2.6 (`kimi-k2.6`) |
| LLM base URL | `https://api.moonshot.ai/v1` |
| VPS | `82.38.68.101` (SSH port 2222) |
| Container port | `8080` (host: `8081`) |
| Deploy user | `openclaw-v3` (uid 1002) |
| Data dir | `/data/projects` (container) |
| Logs | `/var/log/openclaw` (container) |

---

## Commands for Live Testing

```bash
# Check bot status
curl http://82.38.68.101:8081/health

# View recent messages
cd /home/bryan/openclaw-v3
export $(grep -v '^#' .env | xargs)
MATRIX_ROOMS="!GGnkLXZSGwvdXdlnFO:hoomestead.com" python scripts/fetch_messages.py

# Tail bot logs
ssh -p 2222 -i ~/.ssh/vps_deploy root@82.38.68.101 \
  "docker logs openclaw-v3 --tail 30 -f"

# Restart bot
ssh -p 2222 -i ~/.ssh/vps_deploy root@82.38.68.101 \
  "systemctl restart openclaw-v3.service"

# Check systemd status
ssh -p 2222 -i ~/.ssh/vps_deploy root@82.38.68.101 \
  "systemctl status openclaw-v3.service --no-pager"
```

---

## Testing the Bot in Matrix

Send these messages to `@openclaw:hoomestead.com` in the main room:

| Test | Message | Expected Response |
|------|---------|-------------------|
| Identity | `who are you` | "I'm Nexus, your Matrix bot..." |
| Ping | `!ping` | `pong` |
| Help | `!help` | List of commands |
| Status | `!status` | "No active projects." (or list) |
| Plan | `!plan github.com/owner/repo` | Creates project room |
| Chat | `explain Kubernetes` | Helpful answer as Nexus |

---

## Notes for Next Session

1. **Priority 1 is the tool loop.** Without it, agents can't actually do work.
2. **Kimi supports function calling** — use it for tool dispatch instead of parsing text.
3. **Workspace is disk-persistent** — agents can read/write across subprocess restarts.
4. **Identity lock works** — the system prompt approach with strong language is effective.
5. **v2 and v1 are fully stopped** — only v3 should be running on VPS.
6. **209 tests** give confidence for refactors, but integration tests are missing.
7. **The Pocock pipeline** (grill-me → to-prd → to-issues → tdd) is documented but not yet executed end-to-end by the bot itself.

---

*End of status document. Ready for next session.*
