# DSH local agent adapter — historical development observations

**Superseded integration status:** see [the current hybrid integration report](hybrid-agent-integration-report.md). The observations below describe the earlier adapter stage; its outstanding-work list and simple model allowlist are historical. Current code adds capability-gated routing, durable events, profiling, mixed native execution and the external read-only bridge. No live deployment has occurred.

The official `deepseek-harness-sdk==0.2.2rc2` was installed into a separate development virtualenv. No live services, user DSH configuration, provider credentials, tasks or worktrees were replaced. This change is uncommitted and not deployed.

`dsh_runner.py` uses the official SDK's agent loop and JSON-RPC notification stream on demand. The adapter selects an explicitly configured local OpenAI-compatible provider at Ollama's loopback endpoint. It patches the shipped minimal profile to disable persistent shell, file/image tools and working-directory tools. Its only execution tool is the Syntropic read-only MCP bridge. SDK sessions are isolated execution artifacts under the task revision; Hermes remains the authoritative scheduler. No Codex/Claude credential is passed into DSH.

`dsh_tools.py` resolves paths against the repository scope, rejects traversal, symlink escapes, hidden files, credentials and oversized files, and returns a content hash. A DSH handoff must contain a successful read-tool result whose hash still matches the file; the agent's interpretation is not treated as independently verified fact. Native shell, Python, arbitrary external MCP execution and filesystem writes are not enabled in this adapter.

A real `lfm2.5-thinking:latest` run discovered `mcp__syntropic__read_file`, read `fact.txt`, and returned its actual value (731) and SHA256. The full SDK event trace was retained locally. Two repeat LFM file-grounding runs also passed, but two skill/multi-step attempts failed acceptance: one skipped the skill, the other treated the skill itself as the dataset. LFM therefore remains inference-only in the default configuration. A real Gemma4 run read SKILL.md, discovered measurements.txt, read it and returned the correct value (942) and dataset SHA256 in 44.650 seconds. This proves one bounded skill-guided multi-step execution, not broad reliability. Repeat evaluation is in `benchmarks/local_agents.py`, comparing direct inference with the DSH loop on the same small grounded question. Missing RAM, CPU and TTFT measurements are explicitly null. The direct-inference path receives reference data upfront; the DSH path retrieves it. This is not a general routing benchmark.

The existing delegate worker optionally uses DSH when `dsh.enabled` is true, an absolute `dsh.python` is configured, and the selected `dsh.model` (or local default) is in the operator's `verified_tool_models` allowlist. It otherwise keeps its existing inference-only analysis path. The existing process launch gate, worker timeout, cancellation, revision check, dependencies and completion fencing still wrap the child. Actual DSH notifications remain in `local-agent.log`, inspectable through the existing task artifacts UI; a live normalized event-replay API has not yet been added.

To prepare an isolated environment:

```sh
python3 -m venv /path/to/dsh-venv
/path/to/dsh-venv/bin/pip install deepseek-harness-sdk==0.2.2rc2
```

Keep the sample configuration disabled until the exact host/model passes tool and permission probes. The SDK inherits environment by default; the dedicated runner explicitly clears unrelated variables before starting it. The SDK runtime is trusted third-party executable code. The profile's disabled tool surface is not an OS sandbox against a compromised runtime. Use trusted scopes only.

Hermes is retained: the existing regression evidence establishes its claims, dependency/history semantics and crash fencing. A replacement would require a reversible migration and equal recovery evidence; no measured advantage currently justifies risking historical state. DSH's session JSONL and process-local Jobs do not replace durable task ownership.

Additional changes include Thai explicit intent rules, Thai financial-action blocking and an ambiguous-classifier abstention path. These are policy regressions, not a multilingual intelligence benchmark.

Still outstanding: normalized live/replayed events, a registry-backed local-agent routing policy, independent DSH skill providers, a scoped bridge to configured external MCP tools, repeated representative Thai/English evaluations, native session continuation comparisons, actual mixed DSH/native end-to-end execution, process-tree/GPU resource profiling, and physical iPhone/private network verification. Existing Tailscale Serve administrator restrictions remain an external blocker. No unsupported integration is presented as production-ready.

## Current results and acceptance limits

- Baseline: 48 backend tests passed in 53.117 seconds. Current regression: 53 tests passed; exact final timing is retained in local `evidence/system/regression.log`. Frontend strict build and four component/security checks passed. No React view or live service was replaced.
- Real direct inference: two grounded results, 6.038 and 6.819 seconds. Real DSH/LFM single-read results: two grounded tool executions, 24.658 and 17.561 seconds. Both comparisons use a tiny synthetic file, not representative real-work quality.
- Real Gemma4 skill/data two-read case: correct sources and answer in 44.650 seconds. Two LFM multi-step attempts failed the required skill/data contract despite SDK completed outcomes. SDK completion is never treated as factual verification.
- An actual DSH/Gemma4 child also completed through the existing Hermes worker/process gate in an isolated disposable state. The lead plan in that smoke test was explicitly a fixture; this is not a real mixed native/DSH lead demonstration. Source hashes were checked before the child completed.
- Tailscale Serve readback is currently `{}`. No remote endpoint or physical iPhone success is claimed.
- Peak process-tree RAM, GPU allocation, CPU and TTFT remain unmeasured. The benchmark writes null rather than invented values. No provider-quality or scheduler-performance ranking is inferred.

The full requested system overhaul remains incomplete: broad routing evaluation, normalized live event replay and a real native-lead/DSH mixed run are still required. The new local runtime path is an opt-in development integration, not a production readiness claim. All changes remain local for review.
