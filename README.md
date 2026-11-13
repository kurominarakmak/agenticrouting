# Personal AI Work · Syntropic

A working self-hosted chat application with durable background execution, based on the supplied Stitch designs. It extends the installed Hermes task kernel and runs official subscription-backed coding CLIs. Runtime data, knowledge and UI state remain local; choosing a frontier runtime sends its explicitly permitted task context to that provider.

## Open and operate

Source and design assets are in this repository.

```sh
cd agenticrouting
python3 ops.py install
python3 ops.py status
```

Open **http://127.0.0.1:8787**. Choose the local token file:

`~/Library/Application Support/Personal AI Work/state/token`

The app also accepts pasting that token. It is a credential; never put it in a URL or send it to another service. On first install, `ops.py` creates a private local `config.json` from `config.example.json`; edit that file to match installed providers and local paths. Both `config.json` and runtime state are excluded from Git. The installed runtime and state live in `~/Library/Application Support/Personal AI Work`. User repositories outside this app are never moved.

`ops.py install` updates the app's own installed files, preserves its live task history, refreshes application notes/demo retrieval, and installs two **user LaunchAgents**. They restart after process failure and start after your macOS login. `python3 ops.py restart` redeploys; `python3 ops.py stop` unloads these two services and preserves data. Source changes take effect after redeployment and a browser reload.

For foreground diagnostics, stop the services and run the installed `app.py serve` and `app.py worker` in separate terminals. Logs live under the installed `state/logs/`. Do not run a second production worker against the same state directory.

## What works

- Unified chat with persisted conversations, streamed local responses, source cards, actual task cards and independent verification receipts. No manual question/job selector.
- Local deterministic answers or Ollama/LM Studio inference; demanding questions can use a supported subscription inline without becoming a task.
- Five board columns: **To Do → In Progress → In Review → Blocked → Done**. Internal statuses include planning, running, verifying, awaiting approval, paused, failed, cancelled and dependency waits. Failed/cancelled history remains filterable.
- Sidebar active tasks above recent conversations. Chat, board and inspector all read the same persisted records. No invented percentages or quota values.
- Durable Hermes tasks, atomic claims, isolated Git worktrees, external acceptance commands, logs, artifacts, cancellation, pause/resume, bounded owner-requested retries, review gates and follow-up revisions.
- A capable subscription lead can create up to three read-only local analysis subtasks. Hermes dependencies gate the original task until handoffs arrive. Child execution is inference-only, depth is limited to one, and model output is never executed as a local command. This path was tested with real Codex and Ollama.
- Scoped retrieval over allowlisted text/code/documents, CSV/TSV samples, DOCX, PDF when `pdftotext` is available, and read-only SQLite schema metadata. SQLite FTS5 retrieval, source hashes, timestamps and explicit frontier-sharing scope; no cloud embeddings. Preferences, evidence and skills remain distinct typed memory.
- Official MCP SDK client using the existing Hermes environment. Stdio and Streamable HTTP, paginated discovery, per-server credentials and explicit read-only tool allowlists. Financial transaction tools are denied independently of prompts.
- Persistent notification inbox, opt-in browser alerts, and a durable optional authenticated notification-webhook outbox for closed-browser delivery. No push destination is enabled by default.
- Exact-origin private HTTPS support, token authentication, bounded child processes, hard-crash cleanup, and idle-sleep inhibition while an execution child is running. `caffeinate` does not guarantee lid-closed operation or execution while powered off.

## Try it

1. Ask “How many legs does a dog have?” — deterministic, no model call.
2. Ask “What is 2 plus 3?” — local streamed inference.
3. Ask “Implement greeting.py with greet(name), returning Hello, Ada! for Ada and Hello, friend! for an empty name.” — durable coding task in the disposable demo repo.
4. Add “Use multi-step repository analysis and delegate a small context inspection to the local model” to exercise the subscription lead/local handoff path.
5. While work is unfinished, send “Add empty-name handling” in its original conversation. It updates that task, fences the old revision and preserves its worktree.
6. Open Knowledge, sync an allowlisted source and search it. Save preferences separately from factual evidence.

The demo acceptance script is outside the writable worktree and independently checks both greeting cases. For real repositories, configure an acceptance command that actually proves the requested behavior. A passing generic suite is not proof of every new feature; enable owner review where that distinction matters. Research reports require source/claim review rather than claiming factual verification from an LLM summary.

## Runtime and subscription configuration

Edit the source `config.json`, then run `python3 ops.py install`.

- **Codex:** existing ChatGPT login works. Official `codex exec`, forced ChatGPT authentication, filtered environment, sandbox and disabled inherited apps/plugins. No API key fallback.
- **Claude Code:** adapter uses the unmodified official CLI, restricted tools/settings and an isolated authentication check. Complete the official login flow for that profile (for example `claude --setting-sources '' auth login --claudeai`) and refresh Models; do not copy or extract OAuth tokens. A successful profile turn is required to verify access.
- **GLM Coding Plan:** disabled until configured. The adapter uses the officially supported Claude Code integration with the exact documented Coding Plan endpoint, a separate `CLAUDE_CONFIG_DIR`, a dedicated owner-only plan-key file, explicitly confirmed model entitlement and no other provider's environment. No GLM key or plan entitlement was supplied, so real execution is unverified. Follow [Z.AI's supported Claude integration](https://docs.z.ai/devpack/tool/claude) and [plan restrictions](https://docs.z.ai/devpack/faq); unsupported tools, endpoints or models can fall outside plan coverage.
- **Local:** actual Ollama model inventory is discovered; configured default is `lfm2.5-thinking:latest`. LM Studio is discovered on its loopback endpoint when running. Local inference alone is never advertised as a general write-capable harness.

Quota remains `unknown` unless observed through a runtime error. No token-count-to-dollar estimate or unlimited entitlement is invented. Runtime selection checks compatibility and availability before applying conservative heuristics; outcome counts are retained, with small samples explicitly not treated as a quality benchmark. Failures do not automatically trigger another provider. Existing account-level extra-usage/billing settings are not silently modified or asserted to be controlled by this app.

For GLM, configure `glm.enabled`, `plan_entitlement_confirmed`, an actually included `model`, and `confirmed_plan_models`. Put the user-provided plan key in the installed `state/secrets/glm.json` as `GLM_CODING_PLAN_KEY`, mode `0600`. The defaults contain no model name or entitlement assertion. Keys only enter that supported CLI's environment, never a custom inference API client, Codex, the verifier or an unrelated MCP process.

## Knowledge, tools and permissions

`knowledge_roots` is the allowlist. The sample roots cover this app's notes, its demo repository and (if present) existing personal skills. Personal skills are local-only and are not indexed until explicitly synced. Symlinks, hidden directories and secret/credential/config filenames are excluded; changed or removed sources are rejected at retrieval until resynced. `share_frontier: false` keeps a source or memory out of frontier handoffs. Explicitly allowlisted root contents remain sensitive; do not mount broad directories containing unrelated private material.

`mcp_servers` starts empty. Add an existing authorized server, for example:

```json
{
  "my_readonly_server": {
    "enabled": true,
    "transport": "stdio",
    "command": "/absolute/path/to/server",
    "args": [],
    "finance": false,
    "allowed_tools": {"an_actual_read_tool": "read"},
    "secret_file": "my-server.json",
    "env": {"PROVIDER_TOKEN": "secret:PROVIDER_TOKEN"}
  }
}
```

For Streamable HTTP, use `transport: "streamable-http"`, a configured HTTPS `url`, and optional `headers` such as `Authorization: "secret:AUTHORIZATION"`. Secret files must be owner-only JSON files under the installed `state/secrets/`. They are never returned in the registry. Absent secrets fail closed. Tool descriptions and read-only annotations are untrusted metadata; the operator's exact allowlist controls invocation. Use servers whose tool implementation really enforces read-only behavior. Stdio MCP servers are trusted executables and run under your account.

This supports GitHub, Webull, Binance, Google Drive and Figma through their supported, configured MCP servers; it does not inherit this authoring chat's connector sessions. None of those service credentials were provisioned. The tested MCP server was clearly labelled a local protocol fixture, not a market-data provider. Missing live data is reported honestly.

## Notifications and private iPhone access

The bell contains durable completion, blocker and approval records. Browser notifications are opt-in. For closed-browser push, configure an authenticated ntfy-compatible HTTPS topic in `notification_webhook`, set `enabled: true`, and optionally supply `secret_file` with an `AUTHORIZATION` header value. Default payloads omit task titles; enabling title sharing is explicit. The outbox retries at most three times and records endpoint acceptance/errors. HTTP acceptance is not proof of device delivery. No real external push provider or iPhone delivery has been tested.

```sh
python3 ops.py remote
```

If Serve is enabled for the tailnet, this command creates a private Tailscale HTTPS proxy on port 8443 and allows that exact `.ts.net` origin. If the tailnet administrator has disabled Serve, the app reports the blocker and does not claim a remote endpoint. It never enables Funnel, opens a public listener or removes token authentication. Connect the iPhone to your tailnet, open the printed HTTPS URL and authenticate. iPhone network access, ACLs, sleep/lid behavior and closed-browser push require separate verification.

## Verification and limits

Run `python3 -m unittest discover -s tests -v`. See [verification](docs/current-verification.md) and [system boundaries](docs/current-architecture.md).

Tasks are serial within one installed state to conserve local memory and prevent conflicting workers. Concurrent chat submissions are supported. A hard-crash child launch gate records process identity before execution; recovery terminates recorded processes and pauses interrupted work for inspection, without replaying external side effects. Coding sandboxes restrict writes, but Codex may still read host-user-accessible files: use trusted repositories. Artifact/test fingerprints detect worktree changes after verification. No merge, publication, trade, transfer or arbitrary external write executor is enabled.
