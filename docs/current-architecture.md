# Current integrated system

This document describes the implemented application; the earlier architecture/proposal files are historical.

## Reuse and modules

- Existing Hermes `kanban_db` at the pinned installed revision owns task schema, transitions, run history, comments, dependencies and atomic claims. No existing Hermes configuration, auth files, databases or upstream code were modified.
- `app.py` retains the original persistent chat/task adapter, official Codex authentication, worktrees, verifier, cancellation and revisions. Additive migrations preserve existing records. It now serves authenticated APIs, streams local output, distinguishes inline reasoning from durable work, fingerprints verification, and cleans up child groups.
- `services.py` supplies observed runtime inventory, capability compatibility, scoped FTS retrieval, typed memory, official-SDK MCP integration and durable notification delivery.
- `workflows.py` validates bounded lead-generated plans, dispatches inference-only local children through Hermes dependencies, resumes the original task with handoffs and records review/approval state. Only typed local analysis operations are delegated; model text never becomes an executable command.
- `child_runner.py` waits for the parent's durable launch receipt before exec. No inherited lifetime lock can strand a replacement worker. Process identities fence cleanup against PID reuse; the worker lock still excludes concurrent writers.
- `mcp_bridge.py` reuses the MCP SDK already installed with Hermes. `local_runner.py` makes local inference cancellable by the independent worker.
- `index.html`, `style.css`, `app.js`, `components.js` implement the supplied seven-screen visual reference using locally bundled Inter/JetBrains Mono, responsive navigation and controlled DOM components. No model-generated HTML, remote scripts, fake task metrics, or external font requests at runtime.
- `ops.py` installs only this application's runtime under Application Support and two user LaunchAgents. The source remains in Downloads. Existing user repositories are not relocated.

## State and data flow

The installed `state/tasks.db` contains Hermes tables plus additive application tables for conversations/messages, routing decisions, jobs, knowledge/chunks, memory, notifications and tool-call audit metadata. The installed state is authoritative. SQLite's upstream safety check selects rollback journaling on this machine's SQLite 3.49.1; the app does not override that protection.

Chat → local/direct triage → inline answer/tool lookup or durable task. Demanding questions can remain inline. Durable work → atomic worker claim → optional subscription lead → at most three read-only local children → dependency-gated original execution → external acceptance → done or owner review. The lead and children use actual scoped repository observations. Quantitative work without an allowlisted historical dataset blocks before claiming a backtest.

Five UI columns normalize internal states without losing them. Failed/cancelled/paused work remains visible. The sidebar, chat cards and board all read the same backend snapshot. User follow-ups revise the original unfinished root, cancel only unfinished obsolete delegates, retain completed handoffs, and fence stale completion. Review follow-ups reopen the same task for rework. Pause/resume propagates through active dependencies, not historical completed children.

## Security and billing boundaries

Loopback binding; bearer token on private data APIs; exact Host/Origin checks; an optional exact Tailscale HTTPS origin; no wildcard CORS, token URLs, public shell endpoint or Funnel. Static scripts/fonts are bundled, and CSP allows only local scripts. Dynamic text, tables, source cards and tool results become controlled DOM nodes.

Official Codex is forced to ChatGPT authentication with user runtime configuration/rules and inherited apps/plugins disabled. Claude uses official restricted mode with native subscription auth. GLM uses only the documented Coding Plan endpoint via the supported Claude harness after explicit entitlement/model configuration, isolated credentials and profile. Credentials are passed to that CLI only; no subscription-token extraction, proxy or custom metered inference client exists. Model access is established per successful turn, never from a catalog or login alone. No provider fallback follows a failure.

Repositories, verifier argv, knowledge roots, MCP executables/endpoints and read-only tool permissions are operator configuration. Project `.codex/config.toml` is refused before coding execution. Verification executes inside the official workspace sandbox, and changed-file fingerprints are checked before owner review acceptance. The writable worktree is not an all-read privacy sandbox. Untrusted repositories need a stronger OS/container boundary; the application does not claim otherwise.

Knowledge retrieval verifies current path scope and source hashes, and filters non-shareable sources/memory before frontier handoffs. Preferences remain labelled as preferences. MCP outputs, plans and retrieved content are untrusted. Exact tool allowlists and the transaction denial operate outside prompts; trusted server implementation is still required to make a named read operation truly read-only.

## Operational boundaries

Independent launchd workers continue after browser disconnect and restart after process failure while the user session and machine are online. Active child execution inhibits idle sleep; power-off or lid-closed behavior is not solved by an app. Unknown side effects are never automatically replayed. Retries are bounded by both application attempts and Hermes' circuit breaker.

The notification outbox is durable, optional and off by default. Browser alerts require permission. A configured authenticated push endpoint can accept delivery while the browser is closed, but endpoint acceptance is not proof of phone delivery. Tailscale Serve readback must establish the proxy before a remote URL is reported. This tailnet currently requires administrator enablement; no remote access success is claimed.
