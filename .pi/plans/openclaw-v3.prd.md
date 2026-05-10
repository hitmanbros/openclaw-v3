# OpenClaw v3 — PRD

## Problem Statement

OpenClaw v2 is a multi-bot system where seven distinct Matrix identities (Ori, Sage, Forge, Chief, Lens, Pulse, Atlas) run as peer agents in a single Python process. They communicate via Matrix envelopes, debate in shared rooms, and vote on decisions. This architecture has proven difficult to manage: seven Matrix users mean seven sync loops, seven access tokens, complex room membership, and cross-bot delegation overhead. The "team of bots" fiction creates ambiguity — Ori and Chief both route, Forge and Sage both plan, and consensus mechanisms (vote, debate) slow down execution.

The user wants a single Matrix identity that behaves like one competent assistant but internally dispatches subagents for specialized tasks. The bot should follow the proven pi pipeline (scout → planner → slicer → orchestrator → worker → reviewer → tester) with a main orchestrator called Nexus that handles general chat, spawns project rooms, aggregates status, and escalates serious issues. The user also wants tight integration with their custom Matrix client (hoomestead-chat) which supports custom HTML rendering and custom event types for a future dashboard.

## Solution

Build **OpenClaw v3**: a single Matrix bot (`@openclaw`) written in Python with an asyncio core. The bot runs in one headless process on a VPS, listens on Matrix, and internally dispatches subagents using disk-persistent IPC (workspace JSON + inbox messages) — matching the pi harness pattern but adapted for Python.

**Nexus** is the main orchestrator in the primary Matrix room. It answers casual questions, detects project intent, and can spawn isolated project rooms. Each project room gets its own orchestrator that runs the full pi pipeline: scout reconnaissance, planner PRD creation, slicer decomposition, parallel worker execution, reviewer gates, and tester validation. Project rooms are isolated — their own workspace, memory, and budget. When a project is done, the user closes it and the room is archived.

The bot auto-forks GitHub repos per project, edits in an isolated workspace, and only commits to the fork after a phase passes review. Workers run in separate Python processes for isolation; the orchestrator stays in the main process tied to the Matrix event loop. Before each worker runs, the orchestrator snapshots the workspace via file copy for rollback on crash or failure.

A minimal HTTP status endpoint (`/health`, `/status`) runs alongside for monitoring. Structured JSON Lines logs are written for a future dashboard. The custom hoomestead-chat client receives both standard `m.html` messages and custom `com.openclaw.*` events for rich rendering.

## User Stories

1. As the owner, I want to chat with a single Matrix identity (`@openclaw`), so that I don't manage seven bot users and rooms.
2. As the owner, I want Nexus to answer general questions without spawning a full project pipeline, so that casual chat is fast and cheap.
3. As the owner, I want to type `!plan fix the login flow for github.com/me/myapp` to start a project, so that Nexus auto-creates a project room, forks the repo, and begins the pipeline.
4. As the owner, I want project rooms to be fully isolated, so that one project's context, memory, and budget don't leak to another.
5. As the owner, I want the planner to produce a PRD and the slicer to break it into slices before any code is written, so that I can review the plan and catch bad architecture early.
6. As the owner, I want HITL gating on destructive operations and the initial PRD review, so that I maintain control over irreversible changes.
7. As the owner, I want the orchestrator to auto-escalate to Nexus (and then to me) when a project is blocked or a safety-critical operation is requested, so that I know when intervention is needed without checking every room.
8. As the owner, I want workers to run in isolated processes with file-copy snapshots before each slice, so that a crashing or runaway worker doesn't corrupt the project or bring down the bot.
9. As the owner, I want per-project budget caps and pre-project cost estimates, so that I don't get surprised by API bills.
10. As the owner, I want the bot to auto-resume active projects on restart, so that VPS reboots or deploys don't lose work.
11. As the owner, I want to type `!close project Alpha` to archive a project room, so that finished projects don't clutter my room list.
12. As the owner, I want status updates in the project room (slice-level heartbeats) and detailed logs in the ops room, so that I can follow progress at a glance or dig deep when needed.
13. As the owner, I want the bot to post critical errors to the ops room, so that I know immediately if something is broken without checking log files.
14. As the owner, I want a strict bash whitelist for workers with per-project overrides gated by escalation, so that a compromised or confused worker can't `rm -rf` or `curl` malicious payloads.
15. As the owner, I want the planner to write tests, the worker to run them during development, and a separate tester agent to validate the final result, so that there's both iteration context and independent verification.
16. As the owner, I want commits to happen only after a phase passes review, with local worker commits squashed into one clean commit, so that the git history is readable and each phase is atomic.
17. As the owner, I want structured JSON Lines logs alongside human-readable Matrix posts, so that a future dashboard can parse and display real-time project state.
18. As the owner, I want the bot to send custom event types (`com.openclaw.*`) to my hoomestead-chat client, so that my client can render rich widgets (progress bars, dependency graphs, PRD previews) beyond plain text.
19. As the owner, I want custom events to include both structured data and a fallback HTML payload, so that the same event works on desktop (rich HTML) and future mobile (native rendering).
20. As the owner, I want the bot to support natural language commands (`@openclaw what do you think about...`) and explicit `!` prefix commands (`!status Alpha`, `!approve slice-3`), so that I can be casual or precise as needed.
21. As the owner, I want to register project short names (e.g., `Alpha → github.com/me/my-api`) in a config registry, so that I can type `!plan Alpha` instead of full URLs.
22. As the owner, I want the bot to detect project intent from natural language and suggest starting a pipeline, so that I don't have to remember commands for every interaction.
23. As the owner, I want long-term memory via simple SQLite keyword search (not vector embeddings), so that bots can `remember` and `recall` project facts without the complexity of an embedding pipeline.
24. As the owner, I want the Pulse monitor functionality from v2 to run as a cron/scheduled job (not a subagent), so that log scanning and health checks happen without interfering with the main pipeline.
25. As the owner, I want the bot deployed as a Docker container managed by systemd, so that it's portable, restartable, and consistent between local dev and the VPS.
26. As the owner, I want the tool registry, fs tools, shell tools, and budget gate ported from v2, so that proven capabilities are preserved while committee features (debate, vote) are dropped.
27. As the owner, I want agent system prompts loaded from markdown files (like pi's `agents/*.md`) with a shared `BASE.md` and room context injected, so that prompts are maintainable and version-controlled.
28. As the owner, I want the orchestrator to dispatch the entire ready-set of slices in parallel (up to a per-project cap), so that independent work happens concurrently without manual scheduling.
29. As the owner, I want the bot to run entirely headless (no TUI), so that I interact only through Matrix rooms on any device.
30. As the owner, I want auth via environment variables with `.env` files kept locally and on the VPS, so that secrets are injectable and not hardcoded.
31. As the owner, I want to change configuration values (caps, limits, model settings) via Matrix commands without restarting the bot, so that I can tune behavior on the fly.
32. As the owner, I want per-project config overrides (worker cap, budget limits, model choice) that take effect immediately, so that different projects can have different resource policies.
33. As the owner, I want config changes validated before applying, so that a typo in a command doesn't break the bot.
34. As the owner, I want a `!config` command to view and modify settings in real-time, so that I don't need SSH access to tweak behavior.
35. As the owner, I want config defaults documented and easily discoverable via `!config help`, so that I know what knobs are available without reading source code.
36. As the owner, I want configuration persisted to disk automatically when changed via command, so that changes survive bot restarts.
37. As the owner, I want sensitive config values (API keys, tokens) hidden from `!config` output, so that they don't leak in Matrix room history.

## Implementation Decisions

### Architecture
- **Single Matrix identity**: One bot user (`@openclaw`), one sync loop, one access token. Subagents are pure in-process or subprocess constructs with no Matrix presence.
- **Nexus**: The main orchestrator in the primary room. Handles general chat, spawns projects, aggregates cross-project status, and handles escalation. Not a generic `orchestrator` — it has a distinct role as the hub.
- **Project rooms**: Each project gets its own Matrix room with a dedicated `orchestrator` subagent. Isolation includes workspace directory, SQLite memory, and budget counter.
- **In-process + subprocess hybrid**: Orchestrator, scout, planner, slicer run in the main asyncio loop (lightweight coordinators). Workers run as separate Python processes (isolation for filesystem/bash operations). Reviewer/tester can run in-process (read-only, lightweight).
- **Disk-persistent IPC**: Subagents communicate via JSON files — `workspace.json` for shared state, `.pi/inbox.json` for point-to-point messages. Same pattern as pi's harness, adapted to Python file I/O.

### Agent Roster
- **Nexus** — main room hub, chat + project spawn + escalation aggregation
- **Orchestrator** — per-project pipeline dispatcher, computes ready-sets from `blocked_by` graphs
- **Scout** — read-only codebase reconnaissance, maps structure for planner
- **Planner** — writes PRD and implementation plan, bakes tests into the spec
- **Slicer** — breaks PRD into vertical slices with explicit dependencies
- **Worker** — implements one slice end-to-end, RED → GREEN test loop, leaf node (no subagent spawn)
- **Reviewer** — read-only code review against slice criteria and PRD acceptance criteria
- **Tester** — runs tests independently to validate worker output
- **Security-auditor** — conditional, runs on auth/secrets/input-parsing changes
- **Communicator** — drafts user-facing summaries after pipeline completion
- **Caveman** — token-saving wrapper for high-volume mechanical tasks

### Matrix Client
- Port v2's `matrix-nio` asyncio client, stripped to single-bot operation.
- Two room types: **main room** (1:1 with owner, Nexus lives here) and **ops room** (system logs, status dumps, error alerts).
- Project rooms are created dynamically with a `com.openclaw.project` state event containing project metadata (name, repo URL, status).
- Custom HTML messages (`m.html`) for rich rendering in hoomestead-chat.
- Custom event types (`com.openclaw.slice_update`, `com.openclaw.status`, `com.openclaw.dashboard`) with structured data + `render_as` hint + `fallback_html` for cross-platform support.

### Tool System
- **Pruned per agent**: Worker gets `read`, `edit`, `write`, `bash`. Scout gets `read`, `grep`, `find`, `ls`. Orchestrator gets `read`, `write_workspace`, `read_workspace`, `subagent`. Reviewer gets `read`, `grep`, `find`, `ls`. No debate/vote tools — single bot, no consensus needed.
- **Bash whitelist**: `python`, `pytest`, `node`, `npm test`, `cargo test`, `go test`, `make`, `git diff`, `git status`, etc. Network, package install, destructive ops blocked. Per-project overrides possible via escalation to Nexus → owner.
- **Tool registry**: Port v2's tool registry with agent-type scoping.

### Memory & State
- **Pipeline state**: `workspace.json` per project — slice statuses, PRD path, results. Ephemeral, managed by orchestrator.
- **Long-term memory**: SQLite per project with keyword search (no embeddings). `remember(content, scope='project')` and `recall(query)` tools.
- **Config**: Split model. Static (`config.yaml`) for Matrix creds, API keys, room IDs, project registry. Dynamic in workspace/SQLite for per-project caps, runtime state.

### GitHub Integration
- **Auto-fork on project start**: Nexus forks target repo to owner's GitHub account. Workers clone the fork.
- **Isolated workspace**: `/data/projects/<room-id>/` per project. Bind-mount opt-in via `!bind` command with Nexus confirmation.
- **Commit workflow**: Workers make local commits during development. On phase verification (reviewer + tester pass), orchestrator squashes to one clean commit and pushes to fork. Nexus can open PR to original repo.
- **Issue creation**: `to-issues` skill creates GitHub issues from the PRD/slices.

### Budget & Cost
- **Per-project cap**: Daily/hourly token limits per room, configurable at project creation.
- **Pre-project estimate**: Nexus estimates cost (slice count × model) and asks owner to approve before starting workers.
- **Global fallback**: Hard ceiling to prevent runaway spend.

### Rollback & Recovery
- **File-copy snapshots**: Before each worker, orchestrator runs `rsync` or `cp -a` to `.openclaw/snapshots/<slice-id>/`. On failure, restores from snapshot.
- **Retry once**: Worker fails → restore snapshot → retry with same instructions. If retry fails, mark slice `failed` and escalate.
- **Auto-resume on startup**: Read workspace, find `running` projects, retry failed/pending slices.

### Logging & Observability
- **Structured JSON Lines**: `/var/log/openclaw/events.jsonl` with one JSON object per line (timestamp, project, slice, agent, status, metadata).
- **Human-readable Matrix**: Slice heartbeats in project room, critical errors in ops room.
- **HTTP status endpoint**: `/health`, `/status`, `/metrics` on a local port for monitoring and future dashboard.

### Deployment
- **Docker container**: Single image with Python, dependencies, and agent prompt files.
- **Systemd service**: Auto-restart, env var injection, journald for stderr.
- **Local + VPS**: `.env` files on both. Same image everywhere.

### Pulse Monitor
- Not a subagent. A scheduled `asyncio.Task` or cron job that tails service logs, scans for errors, and posts alerts to the ops room. No delegation loop, no Matrix envelope complexity.

### Prompt System
- Agent prompts stored as markdown files: `agents/planner/SYSTEM.md`, `agents/worker/SYSTEM.md`, etc.
- Shared `BASE.md` injected into every agent's system prompt.
- Room context (project name, goals, current phase) appended per-room.
- Port pi's exact prompt content and structure.

## Testing Decisions

- **Test external behavior, not implementation details**: Verify that the orchestrator correctly computes ready-sets, that workers produce files matching criteria, that the Matrix client sends the right events. Don't test internal state mutations.
- **Modules to test**:
  - **Orchestrator dispatch logic**: Given a slice DAG, does it compute the correct ready-set? Does it respect the parallel cap?
  - **Workspace IPC**: Can two processes read/write workspace.json safely? Is inbox delivery reliable?
  - **Snapshot/rollback**: Does pre-worker snapshot capture all files? Does restore return the workspace to exact prior state?
  - **Matrix message parsing**: Does command detection (`!plan`, `!status`, natural language intent) produce the right action?
  - **Tool registry scoping**: Does each agent type receive only its allowed tools?
  - **Budget gate**: Does the cap block dispatch when exceeded? Does it reset daily?
- **Prior art**: v2 has pytest tests in `tests/` for tool registry, budget gate, and delegate logic. Port the patterns that test behavior via public interfaces.

## Out of Scope

- **TUI / local interface**: Headless Matrix-only. No terminal UI.
- **Multi-user / shared ownership**: Solo owner only. No auth model for multiple users.
- **Vector embeddings / RAG pipeline**: Keyword-only SQLite memory for v3 MVP. Embeddings can be added later.
- **Real-time streaming of worker output**: Workers run silently, report on completion. Streaming can be added later.
- **Horizontal scaling / distributed workers**: Workers are local subprocesses. No Kubernetes, no remote worker pools.
- **Automatic PR merge**: Bot opens PRs but never merges. Owner merges manually.
- **Mobile client**: hoomestead-chat mobile port is future work. Bot events are designed to support it, but mobile rendering is not built in v3.
- **v2 debate/vote/circuit breaker**: Dropped. Orchestrator retry + HITL replaces them.
- **v2 embeddings / provenance / canary worker**: Dropped. Simpler monitoring (Pulse cron) replaces canary.

## Further Notes

- **Git repo layout**: `agents/` for prompts, `openclaw/` for Python package, `tests/` for pytest, `docs/` for architecture notes, `scripts/` for setup/deploy.
- **Custom event evolution**: Start with 3–4 event types (`slice_update`, `status`, `dashboard`). Add more as the client dashboard grows. Keep a schema registry in `docs/EVENTS.md`.
- **v2 migration**: Not a migration project. v2 keeps running until v3 is proven. No data migration from v2's SQLite or envelopes.
- **Model lock-in**: Kimi 2.6 via API key for all agents. If switching models later, only the LLM client module changes — agent prompts and orchestration logic are model-agnostic.
- **Security**: Workers never see Matrix tokens, GitHub tokens, or owner credentials. Those live in the main process only. Workers operate in isolated workspaces with no network access (firewall rules or sandboxing can be added later).
