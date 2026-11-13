# Verification

## Automated checks

The implementation verification run passed **47 tests**. Coverage includes task routing and persistence, browser disconnects, worker recovery and exclusion, reviews and retries, scoped retrieval and memory, streamed responses, MCP permission boundaries, provider environment isolation, notifications, and private-origin validation. The suite runs with:

```sh
python3 -m unittest discover -s tests -v
```

The MCP protocol fixture uses the installed official SDK and a local test server. It verifies protocol behavior and allowlist enforcement; it does not verify any external provider credentials.

## Provider and end-to-end checks

- The official Codex CLI completed subscription-backed planning and coding.
- Ollama completed real local inference and two bounded read-only delegated analyses.
- A separate operator-owned acceptance command verified the generated greeting behavior. Completion was recorded from the acceptance receipt and file fingerprints.
- The authenticated browser UI showed the same task state as the worker, including its completed local handoffs.
- Claude Code was unavailable under the isolated login profile on the test host. GLM plan credentials and external account MCP credentials were not configured. No billing-API fallback was used.
- Tailscale Serve was disabled by the test host's tailnet administrator, so private HTTPS and iPhone network access could not be verified. The app checks Serve readback and reports that blocker.

Machine-specific run logs, database state, screenshots and credentials are intentionally kept out of the repository. The tests and configuration examples are safe to share; configure real provider access on the host where the application runs.

## Interface and operations

The supplied Stitch screens informed the dark theme, typography, cards, task board and navigation. The connected interface was checked at desktop size and at **390 × 844**; the phone-width document remained within the viewport. This is browser viewport testing, not a physical iPhone test.

On macOS, `ops.py install` installs this application's two user LaunchAgents and stores the runtime and state under `~/Library/Application Support/Personal AI Work`. A forced stop of the idle worker was followed by an automatic launchd restart; task history remained intact and SQLite integrity passed. The computer must remain online and logged in. Active execution inhibits idle sleep, but lid-closed operation and execution while powered off are not guaranteed.

## Limits

An acceptance command proves only its configured contract. Research claims require source review. Coding sandboxes restrict writes, while host-user read access remains broad. Configure trusted repositories, narrow knowledge roots and authorized MCP tools. Quotas, comparative model quality and external phone notification delivery are not inferred when unavailable.
