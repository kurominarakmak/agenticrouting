# Hybrid agent integration report

Date: 16 November 2026. Source: the existing local working tree, including its prior uncommitted changes. All changes remain uncommitted and undeployed. The installed production app, its credentials, conversations, and services were preserved. Development execution used a separate state directory at `/tmp/syntropic-hybrid-acceptance` and HTTP port 8790.

## Outcome and architecture decision

Keep Hermes as the sole durable task owner, the Python control plane, React UI, official native coding loops, and optional on-demand DSH execution. The genuine Luna → Gemma DSH → Luna workflow passed independent acceptance. This establishes integration, not a general model-quality improvement. Delegation cost more time and native turns than the successful direct coding baseline. Prefer deterministic/direct paths for bounded questions; use a native harness for coding; admit DSH only for task classes with recent, repeated, independently accepted evidence for the exact model digest and SDK version. Do not delegate every task.

Feasible implementation and local verification are complete across all six priorities. Real account MCP access, authenticated remote HTTPS, physical iPhone use, and delivered push notifications remain unverified for the external reasons below. GPU allocation is unavailable. These are not reported as passing integrations.

## Model policy and execution budget

The official [GPT-6 Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna), locally available CLI model metadata, and [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) were checked before execution. Every new native inference used `gpt-6-luna`, with supported `-c model_reasoning_effort="medium"`, ChatGPT authentication, and no API fallback. The four official CLI session `turn_context` records independently confirm both fields; see `evidence/hybrid/observed-native-models.json`. The authoring chat's model was not changed.

Exactly **four native inference invocations** occurred: initial standalone baseline, hybrid planning, hybrid implementation, and profiled baseline. No additional native inference was used for recovery, browser checks, or final rescoring. Local `codex sandbox` verification commands are not inference. Source private configuration and example defaults now specify Luna Medium and a finite four-call budget. The isolated service budget is three (hybrid two plus profiled baseline), exhausted; the initial standalone baseline is separately counted. This is an owner execution limit, not a claim about subscription quota.

A transaction bug initially rolled back reservation rows. It was fixed with an explicit commit and a persistence regression test. Two already-observed hybrid calls were backfilled from completed execution traces; `native-budget-recovery.json` records that correction. It did not authorize extra calls. Production's previously installed configuration was not redeployed.

## Evidence and verification

Evidence is local and ignored by Git under `evidence/hybrid/`. `sanitized/` includes safe native/DSH event projections, plans, patches, receipts, verifier results, source inputs, observed model metadata, event replay, per-run resource measurements, benchmark summaries, and a SHA256 manifest. It omits hidden reasoning, raw native command output, private tokens, and benchmark answer bodies. Raw runtime artifacts remain private in the isolated state; they are not intended for publication. Sanitized metadata preserves IDs and acceptance outcomes for cross-checking.

Final checks on the source:

| Check | Result |
|---|---|
| Python regression, DSH, MCP security, routing, events, recovery, profiling | 68 passed, 63.869 seconds |
| Strict TypeScript + Vite build | Passed |
| Component/security tests | 4 passed |
| Playwright against isolated live backend | 6 passed, 12.2 seconds |
| Patch whitespace check | Passed |

Logs are copied into `evidence/hybrid/checks/`. Python fixtures cover protocol/security failure branches; real integration evidence below is distinguished from those fixtures. Existing tests for cancellation, stale revisions, interrupted workers, approvals, native authentication, followups, worktrees, notifications and dependency fencing remain passing. No new live Claude/GLM/account-provider inference was attempted.

## 1. P0: real native lead and local delegation

**Implementation:** `app.py`, `workflows.py`, `services.py`, `control.py`, `dsh_runner.py`, `dsh_tools.py`. The lead generates bounded actual subtask JSON. Dispatch requires exact compatible capability evidence. DSH receives a scoped read-only bridge; its final prose cannot establish completion. Successful tool records are correlated and current file hashes checked before handoff, then rechecked before native continuation. Native inference is reserved before process launch. Execution IDs, revisions, dependencies, wall limits and process-group cancellation remain enforced. Failure blocks/reviews the task; it never silently switches provider.

**Real evidence:** parent `t_b0efe2fd`, child `t_d9898db3`. Luna independently produced the plan “Cross-check grading rules and fixtures.” Gemma actually read README, rules and cases through DSH tools. The parent received validated source evidence and implemented `scorer.py`. A separate nine-case verifier passed, with original requirements unchanged. The official native session confirms that the local handoff was present in the continuation prompt. `hybrid-result.json`, the preserved plan, patch, receipt and tool-source records document this chain.

Both Codex-only runs used the same requirements and independent acceptance cases: the initial baseline passed; the profiled baseline failed a grade-boundary assertion despite its own claimed success. The hybrid passed. `independent-recheck.json` reran all three checks and verified unchanged input hashes. The boundary at 89.999 rounding to 90 exposes ambiguity about grading before/after rounding; this small example does not demonstrate superior intelligence. Prompts and harness setup were comparable but not byte-identical; one baseline used standalone CLI, the other the task worker.

The first hybrid submission `t_03633b3c` was blocked before inference because “Do not publish” was misclassified. Narrow negation handling was corrected and tested; the blocked record remains preserved. This was not a hidden failed inference retry.

**Acceptance:** real delegation, tool use, validated continuation, independent completion, durable history, bounded calls, and no paid fallback passed. Fake/missing tool evidence, changed sources, stale execution IDs and cancellation are covered by deterministic regressions. Real worker kill/restart is described in section 4. Latency was 175.986 seconds, versus 49.956 seconds for the successful standalone baseline. Native phases used 7.727 and 56.134 seconds; DSH used 110.479 seconds. Some early hybrid execution overlapped an subsequently aborted local benchmark; timing is observational, not a controlled speed comparison.

**Risk/blocker:** no external blocker for this local integration. No general quality or cost advantage is established; only one genuine hybrid coding example was run to conserve subscription usage.

## 2. P0: repeatable local capability evaluation

**Implementation:** `benchmarks/capability_eval.py`, `direct_probe.py`, `direct_eval.py`, `project_audit.py`, `hybrid_acceptance.py`, `acceptance.py`, `verify_scorer.py`, and the immutable scorer fixture. The official optional SDK is pinned in `requirements-dsh.txt`. Five task classes run twice per model: single file retrieval, multi-file sum, skill loading followed by two reads, missing-file recovery, and Thai multi-file instructions. English is used in the other cases. MCP transport is exercised by real DSH file retrieval and the separate external fixture. The controller checks actual tool traces, required sources, current SHA256s and visible final answers. Runtime “completed” is never sufficient.

**Repeated results:** main evaluation sets, not the aborted partial benchmark:

| Task class | Gemma DSH | LFM DSH | Gemma direct | LFM direct |
|---|---:|---:|---:|---:|
| Single file | 2/2 | 2/2 | 2/2 | 0/2 |
| Multiple files | 2/2 | 1/2 | 2/2 | 0/2 |
| Skill method | 1/2 | 0/2 | 2/2 | 0/2 |
| Missing-file recovery | 2/2 | 0/2 | 2/2 | 0/2 |
| Thai | 1/2 | 0/2 | 2/2 | 0/2 |
| Total | 8/10 | 3/10 | 10/10 | 0/10 |

Direct inference receives all scoped reference data upfront and invokes no tools. Its “skill/recovery” columns test supplied context, not autonomous discovery or recovery. DSH retrieves references through its agent loop. Direct requests explicitly use 8192 context; the SDK advertises 8192, but observed Ollama residency reported a 4096 server context for DSH. These contracts differ. The tiny tasks are plumbing/capability checks, not a broad intelligence benchmark.

A final acceptance review found that LFM emitted `<think>` content through its normal content channel. The initial direct checker incorrectly found expected values inside that reasoning. `acceptance.py` now excludes reasoning (and incomplete reasoning-only outputs), checks standalone numerical values, and has a regression test. All saved outputs were rescored without inference; all ten LFM direct successes became failures. `acceptance-correction.json` preserves the correction; the displayed table uses corrected results. DSH acceptance counts did not change. Raw reasoning is excluded from the shareable evidence and live event API. Older append-only raw benchmark logs must not be used instead of the corrected results JSON.

Additional independent sets are kept separate: repeated multi-file resource runs (Gemma 2/2, LFM 0/2); fresh digest-bound Gemma multi-file runs (2/2); and an actual project configuration/hash audit (Gemma direct 2/2 and DSH 2/2; LFM direct 0/2 and DSH 0/2). LFM DSH audit responses fabricated configuration while making zero tools calls; independent verification rejected them. These are recorded failures, not retried successes.

**Failure causes:** absent tool calls; missing required skill/data reads; incorrect/missing final hashes or result; incomplete visible output at the requested token cap; malformed JSON on the real project audit. The separate missing-file test requires an actual errored tool response before successful recovery. `summary.json` and each run's results JSON retain outcomes, reasons, metrics and log locations. The aborted parallel LFM set `lfm-eval/` is excluded. Historical `docs/dsh-local-runtime.md` observations remain historical.

**Acceptance:** repeatability, task-level verification, real tools/skills/MCP, repeated language cases, classified errors and machine-readable evidence passed. No model is automatically enabled for unsupported classes. Broad Thai/skill reliability failed; no ranking is claimed. Main DSH Gemma latency was 25.273–72.340 seconds; LFM 5.832–41.212 seconds, including failures.

## 3. P1: persisted capability routing

**Implementation:** `control.py` adds capability and native-call tables inside the existing Hermes task database. `services.py` and `app.py` connect observed availability/authentication, model, task class, samples, age, known failures, runtime restrictions and resource observations to request routing. Request dimensions include intent, complexity, tools, skill requirements, context, privilege/risk and permitted execution paths. Existing Thai/English deterministic rules and classifier abstention are preserved. Low-cost direct paths remain available; local-only unsupported work blocks rather than becoming a native request. Selection reasons and evidence IDs are persisted in task routing and surfaced through existing task/registry views.

Eligibility requires at least two passing recent records, no failures among the last ten retained matching observations, freshness within seven days, and current model digest plus SDK identity. Imported evidence retains its original observation/log time, preventing old runs from becoming fresh through reimport. Changed/unknown identity is excluded, not treated as capability. Unknown subscription quota stays unknown. Configured availability alone is insufficient. Registry updates are owner/benchmark operations, not an LLM/browser write API.

**Evidence/tests:** `tests/test_control.py` and routing/language regressions cover unknown/failing/old evidence, changed identity, stale state, abstention, privilege and financial boundaries. `registry-snapshot.json` shows the final isolated state: only Gemma multi-file/scoped-analysis has fresh exact-identity evidence (IDs 15–18). Earlier records without identity remain quarantined. LFM has no eligible records in that state. Production has not imported these development records and is not automatically enabled.

**Fixed-routing comparison:** replay the preserved ten main tasks against the final class gate: fixed Gemma DSH attempts all ten and passes 8; fixed LFM DSH passes 3; the final exact-identity gate admits only the two multi-file tasks, both of which pass (2/2 admitted, 20% local-agent coverage), and abstains from the other eight. This is an offline decision replay using tiny related fixtures, not a held-out end-to-end test or proof that routing raises total success. No paid fallback was executed for rejected tasks. Direct Gemma passes 10/10 with supplied context, demonstrating why tool delegation is unnecessary for that easier contract. LFM's actual configuration-audit failures prohibit claiming it broadly reliable even for direct inference.

**Acceptance:** persisted evidence, fail-closed compatibility, explanation, outcome persistence, sample/recency disclosure and fixed-policy comparison passed. Expected benefit uses conservative class eligibility and deterministic rules; there is no statistically calibrated optimizer or learned resource predictor. Registry query/probe overhead is not isolated in measurements; provider discovery is serialized to avoid simultaneous auth subprocesses.

**Risk:** two samples permit a bounded class, not general reliability. Hardware, provider or tool changes beyond the model digest/SDK can still invalidate evidence; rerun acceptance when these change. Skill/Thai/general external-provider compatibility remains excluded until separately verified.

## 4. P1: durable normalized events and replay

**Implementation:** `control.py`, event endpoints in `app.py`, hooks in `services.py`/`workflows.py`, and React `EventTimeline.tsx`, `main.tsx`, `renderers.tsx`. Events live in the authoritative task database, with task/revision/execution/sequence/time/runtime/model/type and an allowlisted payload. They cover planning/routing/dispatch, tool requests/results, skill read observations, validation, verification, approval, cancellation, failure and completion where the harness emits observable facts. Native reasoning is never projected as an event. Oversized/unsupported records are omitted safely.

`/api/events` returns bounded cursor pages; `/api/events/stream` uses authenticated fetch SSE, heartbeat and reconnect. Tokens stay in headers. Replay is ordered/deduplicated; revision/active execution fencing prevents stale completions. SQLite uniqueness makes repeat log ingestion idempotent after process restart. The React effect aborts streams and clears retries on task/token/revision changes. Chat/sidebar show authoritative activity; inspector replays execution history. An actual lazy-module load failure during browser review exposed a blank workspace: a tested text fallback/error boundary now keeps the persisted reply usable.

**Real evidence:** task `t_0e6f2a6e` was submitted through the actual Chat UI, executed by the isolated DSH worker and observed live in inspector. Desktop screenshots `live-tools.jpg` and `live-events.jpg` show real request/result activity. `mobile-events.jpg` shows a 390×844 viewport without horizontal overflow; it is not a physical iPhone test. A read-only research task ends in review, not misleading independently verified completion.

For `t_b2875331`, an HTTP client disconnected, a real tool request occurred, and the worker was SIGKILLed. Restart stopped its recorded child process group, kept durable events, and blocked the interrupted revision. Explicit followup resumed revision 2, revalidated source hashes and reached review with **zero additional native calls**. `real-recovery.json` records this. Old revision rows remain stored; the current stream rejects stale revisions.

**Acceptance/tests:** concurrency, ordering, source-key deduplication, restart durability, stale revision/execution, host/auth checks and SSE pass in Python. Playwright verifies offline/reconnect/reload ordered replay without duplicates plus live API/inspector/mobile access. Six browser tests passed. `sanitized/events.json` preserves 91 real event rows from these executions. Browser disconnect does not own worker lifetime.

**Resources/risks:** streaming uses a bounded 25-second connection and 0.5-second database polling, no extra persistent service. View retains the last 5000 rendered events; durable rows remain in SQLite. No formal browser INP measurement was taken; passing test duration is not a responsiveness benchmark. Native event coverage is limited to supported observable harness events. Old event revisions remain audit data, not a separate task store.

## 5. P1: resource and latency profiling

**Implementation:** `profiling.py`, `app.run_child`, benchmark runners and per-execution metrics JSON. macOS `ps` samples process trees every 200 ms, with time-bounded sampling. Measurements report wall time, sampled peak RSS and accumulated process CPU seconds. Optional shared Ollama observation is separate: its RSS and CPU delta cannot be uniquely attributed to one request. Short-lived descendants and between-sample peaks can be missed; summed RSS can count shared pages more than once. Native cloud model compute is outside the CLI process tree.

| Mode | Verified Success | Latency | Peak RAM | CPU | Usage | Limitations |
|---|---|---|---|---|---|---|
| Direct local | Gemma 10/10; LFM 0/10 | Gemma 3.206–18.949 s; LFM 9.224–9.935 s | Client ≤23,838,720 B; shared Ollama Gemma ≤4,542,791,680 B, LFM ≤374,276,096 B | Client Gemma .04–.09 s, LFM .13 s; shared Ollama 1.31–20.48 s /16.25–16.71 s | Actual Ollama prompt/eval counts and load/eval nanoseconds in per-run results | Upfront context, no tools; LFM output truncation/reasoning excluded |
| DSH local | Main Gemma 8/10; LFM 3/10 | Gemma 25.273–72.340 s; LFM 5.832–41.212 s | Main child Gemma ≤580,845,568 B; LFM ≤617,857,024 B. Separate multi-file Gemma child ≤592,510,976 B plus shared Ollama ≤4,436,066,304 B | Main child Gemma 2.18–2.94 s, LFM 1.85–4.07 s. Resource subset shared Gemma 17.54–63.34 s | SDK response/tool counts and reported numerical usage where observable | Main ten-run sets omit shared-server memory/CPU; separate resource subset cannot be substituted as the same run |
| Codex-only Luna Medium | 1/2 coding runs | Successful standalone 49.956 s; failed profiled CLI 51.205 s | Successful run N/A; failed run 165,576,704 B | Successful N/A; failed .71 CPU s | 1 native call each; successful 96,146 input/1,959 output tokens, failed 71,992 input/2,094 output | Provider reports include cached input; neither token counts nor CLI RSS measure cloud cost/compute |
| Hybrid Luna Medium + DSH | 1/1 coding run | 175.986 s total; plan 7.727, DSH 110.479, implementation 56.134 s | Observed stage tree maxima: native plan 111,788,032 B; DSH 491,814,912 B; native implementation 154,927,104 B. Shared Ollama N/A for this run | Stage CPU .35 +3.40 +.80 s (4.55 s; verification excluded) | 2 native calls: plan 11,089 input/80 output; implementation 101,548 input/2,257 output; DSH usage not captured in that earlier run | Not aggregate concurrent system RAM; partial competing local load; one example and ambiguous grading boundary |

Direct TTFT (first content chunk, possibly reasoning for LFM): Gemma .109–4.615 seconds; LFM .195–.783 seconds. Fresh identity-bound Gemma DSH visible text-block TTFT: 43.738–49.103 seconds; total 51.314–58.587 seconds. Earlier DSH traces did not collect TTFT: N/A. SDK event timestamps are epoch milliseconds; main Gemma tool call/result latency was .007–.034 seconds (18 observed pairs); fresh multi-file pairs .010–.065 seconds. These exclude model deliberation between steps. Direct Ollama load/prompt/eval timing is provider-reported in `results.json`; DSH inference breakdown beyond visible text blocks is N/A. SDK requested 1024 output tokens, but some reported usage exceeds that; it is not claimed as an externally enforced hard token cap. Wall/tool/turn limits remain external controls.

Idle observation: shared Ollama RSS 38,895,616 B, .01 CPU second over 2.049 seconds without inference. `idle-resource.json` distinguishes this delta from the sampler's lifetime CPU. Active shared-server CPU can exceed wall seconds through multiple cores. GPU/Metal allocation is **N/A**: Ollama's `size_vram=3,228,429,188` is a provider residency report, not independently measured physical GPU allocation. Model disk sizes (Gemma 9,608,350,718 B; LFM 731,163,903 B) are neither RSS nor GPU usage.

**Acceptance:** actual repeated RSS/CPU/wall and latency/usage observations, reproducible profiler, separate shared-server scope and explicit unavailable fields passed. No unsupported GPU estimate or formal frontend responsiveness score is supplied. On constrained Apple Silicon, keep serial workers, bounded contexts/tools, no always-resident DSH service, and require a measured quality reason to pay Gemma's roughly 4.4 GB shared-server RSS. Do not recommend unreliable LFM tool execution merely because it is smaller. Hybrid latency and two native calls here argue for selective delegation.

## 6. P2: external MCP and private mobile operation

**Implementation:** `external_mcp.py`, `mcp_bridge.py`, `manage_mcp.py`, `dsh_tools.py`, `services.py`, `ops.py` support explicit owner registration, discovery with bounded pagination, exact read-tool permissions, provider-scoped secret references, JSON-schema validation, timeouts, process-group cancellation and safe structured results. Redirects/remote schema references are rejected. Credentials are redacted before audit/result hashing. Allowed configuration is refreshed before calls; revocation blocks subsequent calls. Audit rows store response/argument hashes; DSH handoff validation rechecks the authoritative audit record and current permission. MCP metadata/annotations do not grant permission. Financial/action tools are denied independently of model requests.

**Real fixture evidence:** Gemma discovered and called external `fixture.read_number(offset=2)`, received 742 and audit ID 3, and returned provenance hash `60c389229d17b66516ee9ec87add818c2a0d94e9e28e8d4df57aa7047274e51a`. Independent trace verification matched the actual audit row; `external-proof.json` records pass. This is a real protocol exchange against synthetic isolated data, not a connected user account. Two model responses/one tool call were observed; visible TTFT 28.856 seconds. Python tests cover invalid arguments, denied/financial calls, missing credentials, secret echo redaction, revocation, protocol errors and scoped registration. Fixture protocol/permissions acceptance passed.

**Remote audit:** `remote-audit.json` records both existing user LaunchAgents running, Tailscale Serve status `{}`, notification delivery disabled, and zero configured external MCP providers. No live services were restarted or replaced. Existing exact-origin/bearer authentication and notification-outbox retries remain tested. The new source UI/replay works in desktop mobile emulation and after network disconnect/restart in the isolated environment.

**External acceptance/blockers and owner actions:**

- Real account MCP: unverified. Supply an actual authorized read-only server, exact tool allowlist and owner-only provider secret file. Register through `manage_mcp.py` and run provider-specific acceptance before allowing that class. Authoring-chat account connectors are not credentials available to Syntropic.
- Private authenticated remote HTTPS: unverified. Current Serve config is empty; prior setup evidence identifies an administrator restriction. The current read-only status cannot itself prove permission changed. The tailnet administrator must enable Serve; after deployment authorization, the owner can run the existing `ops.py remote` and verify a private endpoint. No Serve mutation, public tunnel or policy bypass was attempted.
- Physical iPhone/mobile-network testing: unverified; no accessible device/network session. Once private access exists, test Chat, task inspector, disconnect/background completion, browser restart and replay on the actual device. The 390×844 screenshot is not a substitute.
- Completion delivery: unverified live; notification webhook is disabled and no delivery channel is authorized. Configure an owner-approved channel and test real delivery after installation. Deterministic outbox/retry/privacy tests passed; no message was sent.

**Risks:** a configured read-only permission is enforceable at dispatch but a malicious owner-selected MCP executable can lie about its behavior. Stdio SDK/MCP processes run as the user; they are trusted third-party executables, not an OS security boundary. Native workspace-write sandboxing is not complete protection against reads of other host-accessible files. Source changes require review before replacing the installed service.

## Reproduction and owner handoff

Use an isolated configuration/state and absolute interpreter paths. The temporary SDK environment used here was `/tmp/syntropic-dsh-env`; a future durable environment should be outside Downloads (for example `~/.local/share/syntropic-dsh-venv`) to avoid macOS background-service folder restrictions. No live installation is authorized by this report.

```sh
python3 -m unittest discover -s tests -v
npm run build --prefix frontend
npm run test:components --prefix frontend
SYNTROPIC_URL=http://127.0.0.1:8790/ui/ SYNTROPIC_TOKEN_FILE=/tmp/syntropic-hybrid-acceptance/state/token npm test --prefix frontend
python3 benchmarks/capability_eval.py --config /absolute/isolated/config.json --state /absolute/isolated/state --out /absolute/new-evaluation --repeats 2
python3 benchmarks/direct_eval.py --inputs /absolute/new-evaluation/inputs --out /absolute/new-direct --repeats 2
python3 benchmarks/project_audit.py --dsh-python /absolute/dsh-venv/bin/python --mcp-python /absolute/hermes-venv/bin/python --out /absolute/new-audit
```

The optional SDK is installed only into a separately chosen environment using `requirements-dsh.txt`. Native acceptance is deliberately explicit and spends subscription turns:

```sh
python3 benchmarks/hybrid_acceptance.py --config /absolute/isolated/config.json --directory /absolute/new-hybrid-run --mode hybrid --capability-results /absolute/new-evaluation/results.json
python3 benchmarks/hybrid_acceptance.py --config /absolute/isolated/config.json --directory /absolute/new-native-run --mode codex-only
```

Capability imports require the original evaluation’s model/SDK identity to match the current runtime; older output lacking that field must be rerun, not relabeled. Each native runner refuses an existing output directory, fixes Luna Medium, and bounds calls (hybrid two, baseline one). It does create a fixture Git commit inside its new isolated test repository; it does not commit this application or touch the remote. A native lead may elect not to delegate; the hybrid runner then fails mixed acceptance rather than inventing a plan. Rerun class acceptance on the intended host/model/SDK before enabling DSH; keep untested classes disabled. No broad benchmark rerun or additional native calls are necessary to review this delivered evidence.

Remaining limits: small related fixtures, incomplete provider/hardware access, sampled resource lower bounds, no GPU telemetry, and an existing large lazy prose bundle warning (~620 kB minified) despite a passing build. Hermes detects the host SQLite version's WAL-reset issue and uses DELETE journaling; no runtime/database upgrade was performed. There is no migration to another scheduler, duplicate agent framework, paid-provider auto-retry, deployment, commit or push in this work.
