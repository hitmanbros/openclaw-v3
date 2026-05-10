# OpenClaw v3 — Current Architecture & Remaining Work

> Last updated: 2026-05-10
> Commit: `923b550`
> Tests: **209 passing**
> Bot: `@openclaw:hoomestead.com` (live on VPS)

---

## Architecture Overview

OpenClaw v3 is a **single Matrix bot** (`@openclaw:hoomestead.com`) that runs an internal subagent pipeline. One identity dispatches ephemeral subprocess agents via disk-persistent IPC.

```
Owner (@bryan:hoomestead.com)
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
│  │     PipelineOrchestrator          │      │
│  │  scout → planner → HITL → slicer  │      │
│  │  → workers → review → test → audit│      │
│  │  → git commit → PR                │      │
│  └───────────────────────────────────┘      │
│                                             │
│  IPC: workspace JSON + inbox JSON (disk)    │
│  LLM: Kimi k2.6 via Moonshot API            │
└─────────────────────────────────────────────┘
```

---

## ✅ What's Implemented (This Session)

### 1. Agent Tool Loop (`openclaw/agents/loop.py`)
The core missing piece. Agents now have a real iterative loop:
- Reads task from workspace
- Calls LLM with tool schemas (OpenAI-compatible function format)
- Parses `tool_calls` from LLM response
- Dispatches to tool registry
- Writes results back as tool messages
- Iterates until completion or max iterations (default 20)

**Tools available to agents:**
| Tool | Agents | Description |
|------|--------|-------------|
| `read` | all | File read with offset/limit |
| `write` | all | File create/overwrite |
| `edit` | all | Exact text replacement |
| `bash` | all | Whitelist + timeout |
| `grep` | all | Content search |
| `find` | all | File glob search |
| `ls` | all | Directory listing |

### 2. LLM Client Upgrade (`openclaw/llm/client.py`)
- `chat()` now returns the raw message dict (supports `tool_calls`)
- `chat_text()` returns just the content string (backward-compatible for chat)
- Token tracking preserved

### 3. Tool Registry (`openclaw/tools/registry.py`, `openclaw/tools/__init__.py`)
- Proper OpenAI-compatible function schemas: `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}`
- All tools registered with descriptions and parameter schemas
- Agent-scoped access (e.g., `reviewer` only gets `read`, `grep`, `find`, `ls`)

### 4. Agent Subprocess Entry (`openclaw/agents/__main__.py`)
Rewritten to use `AgentLoop` for all agents:
- **scout**: Maps codebase with tools, writes report
- **planner**: Reads report, writes PRD to `.pi/plans/project.prd.md`
- **slicer**: Reads PRD, writes slices JSON
- **worker**: Reads slice task, uses tools to edit code, writes result
- **reviewer**: Reviews slice with read-only tools
- **tester**: Runs test commands via bash tool
- **security-auditor**: Audits for auth/secrets/injection risks

### 5. Full Pipeline Orchestration (`openclaw/pipeline/orchestrator.py`)
`!plan` now actually runs the pipeline:
```
!plan github.com/owner/repo
  → Nexus creates project room
  → PipelineOrchestrator starts in background
    → Phase 1: Scout (subprocess)
    → Phase 2: Planner (subprocess) → writes PRD
    → Phase 3: HITL — pauses, asks owner !approve/!reject
    → Phase 4: Slicer (subprocess) → writes slices
    → Phase 5: Dispatch workers (parallel, max 3)
      → For each ready slice: worker → reviewer → tester
      → Security audit runs conditionally (auth/secrets/dependencies)
    → Phase 6: Git squash commit + push (wired, needs fork_url parsing)
```

### 6. HITL Integration (`openclaw/nexus.py`, `openclaw/pipeline/hitl.py`)
- After planner writes PRD, pipeline pauses
- Owner posts `!approve` or `!reject` in project room
- Nexus writes HITL status to workspace
- Orchestrator polls workspace and resumes/rejects

### 7. Config Persistence (`openclaw/nexus.py`)
- `!config get <key>` reads from `data_dir/config.json`
- `!config set <key> <value>` writes to `data_dir/config.json`

### 8. Security Auditor Integration
- `_should_security_audit()` checks slice task/result for keywords: auth, secret, password, token, login, input, dependency, sql, eval, exec, xss, etc.
- If triggered, spawns `security-auditor` subprocess (read-only tools)
- Blocking findings prevent slice from being marked "done"

### 9. Live Matrix Tests (`tests/test_live_matrix.py`)
- Tests against real homeserver (`matrix.hoomestead.com`)
- Verifies bot responds to `!ping`, `!status`, and natural language
- Uses Bryan's owner token (environment variable)

### 10. All Tests Fixed
- 209 tests passing (was 209 before, still 209 now)
- Fixed LLM client tests for new dict return type
- Fixed matrix client tests for `chat_text()`
- Fixed tool registry tests for new schema format
- Fixed orchestrator tests for new constructor + pipeline logic

---

## 🚧 Partially Done / Needs Hardening

### Git Commit/PR Workflow
**File:** `openclaw/pipeline/orchestrator.py::_commit_and_pr()`
- ✅ Squash commit works
- ✅ Push works
- ❌ PR opening not fully wired — needs owner/repo extraction from `fork_url`

### Security Auditor
**File:** `openclaw/agents/__main__.py::run_security_auditor()`
- ✅ Runs conditionally
- ⚠️ Needs real-world testing with actual LLM tool calls
- ⚠️ Keyword-based triggering is crude; should diff actual changed files

### Escalation Manager
**File:** `openclaw/pipeline/escalation.py`
- ✅ Code exists
- ⚠️ Cross-room routing works but thresholds not tuned
- ⚠️ No retry backoff logic

### HITL Gates
**File:** `openclaw/pipeline/hitl.py`
- ✅ Approve/reject workspace state management
- ⚠️ No timeout notification to owner (just silently fails after 1 hour)
- ⚠️ No reminder pings

---

## ❌ Not Yet Implemented

### 1. Live Agent Tool Loop Validation
**Critical.** The tool loop is written but has never been exercised with a real Kimi API key + real tool calls. We need:
- A manual test: spawn a worker with a real slice and verify it can `read` → `edit` → `bash` → iterate
- Verify Kimi's `tool_calls` format matches our parsing exactly
- Verify tool result stringification works for complex return types (dicts, lists)

### 2. End-to-End Pipeline Integration Test
**File:** `tests/test_integration.py`
- Currently tests Nexus in isolation
- Missing: full pipeline from `!plan` through worker dispatch
- Needs mocking of subprocess spawning or a local test harness

### 3. GitHub PR Opening
**File:** `openclaw/github/commit.py`
- `open_pr()` exists but is not called in the pipeline
- Pipeline `_commit_and_pr()` needs to parse `owner/repo` from `fork_url`
- Needs to handle branch naming (not always `main`)

### 4. Multi-Project Coordination
- No `!close <name>` command
- No cross-project resource limits
- No shared budget pool across projects

### 5. Memory / Long-Term Context
**File:** `openclaw/memory/store.py`
- SQLite keyword search exists
- Not injected into agent prompts
- No conversation summarization for long-running projects

### 6. Input Sanitization Hardening
**File:** `openclaw/tools/bash.py`
- Whitelist is basic regex
- No file traversal prevention in `read`/`write`/`edit` beyond workspace path check
- No rate limiting on tool calls per agent

### 7. Deployment Automation
**File:** `Dockerfile`, `docker-compose.yml`
- Code is pushed but VPS service not restarted
- Need SSH + `systemctl restart openclaw-v3.service`

---

## Next Steps (Priority Order)

### Phase 1: Validate Tool Loop (Critical)
1. Set `KIMI_API_KEY` and run a manual worker test
2. Verify agent can read a file → edit it → bash test → complete
3. Fix any Kimi API format mismatches

### Phase 2: Deploy (Critical)
4. SSH to VPS, pull repo, restart service
5. Run live `!plan` test against a trivial repo
6. Monitor logs for pipeline execution

### Phase 3: Harden (High)
7. Wire GitHub PR opening in pipeline
8. Tune security-auditor triggering (file diffs vs keywords)
9. Add integration test for full pipeline
10. Implement `!close` command

### Phase 4: Polish (Medium)
11. Inject memory store into agent prompts
12. Add rate limiting per agent
13. Tune escalation thresholds
14. Write proper end-to-end test with mocked LLM

---

## File Reference

| Purpose | Path |
|---------|------|
| Bot entry | `openclaw/__main__.py` |
| Bot main loop | `openclaw/main.py` |
| Nexus (main room) | `openclaw/nexus.py` |
| Project manager | `openclaw/project.py` |
| Subagent runner | `openclaw/subagent/runner.py` |
| Agent subprocess entry | `openclaw/agents/__main__.py` |
| **Agent tool loop** | `openclaw/agents/loop.py` |
| LLM client | `openclaw/llm/client.py` |
| Prompt loader | `openclaw/llm/prompts.py` |
| Matrix client | `openclaw/matrix/client.py` |
| Command parser | `openclaw/matrix/commands.py` |
| Tool registry | `openclaw/tools/registry.py` |
| Tool registration | `openclaw/tools/__init__.py` |
| Pipeline orchestrator | `openclaw/pipeline/orchestrator.py` |
| Dispatcher | `openclaw/pipeline/dispatcher.py` |
| HITL gate | `openclaw/pipeline/hitl.py` |
| Escalation | `openclaw/pipeline/escalation.py` |
| Git commit/PR | `openclaw/github/commit.py` |
| Agent prompts | `agents/*.md` |
| Tests | `tests/*.py` |
| Config | `config.yaml` |
| Live tests | `tests/test_live_matrix.py` |

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
