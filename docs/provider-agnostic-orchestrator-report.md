# Provider-agnostic orchestration implementation report

## Scope and boundaries

This work adds provider-neutral bounded inference adapters, a strict Supervisor proposal contract, per-role model and effort snapshots, an independent Reviewer loop, finite call and wall-clock budgets, and local PR preparation/delivery controls on top of the existing Hermes task kernel. The UI exposes provider, role, policy, and repository delivery settings in the existing Stitch-style React interface.

The terms remain separate in implementation and operator configuration:

- **Provider** means an explicitly enabled API endpoint and protocol adapter: Ollama, LM Studio, OpenAI-compatible chat completions, OpenAI Responses, or Anthropic Messages.
- **Model** means an exact configured or observed model identifier. No model name is inferred from a provider label.
- **Harness** means a runtime that executes a task. Provider API adapters have no shell or write tools; supported native CLIs are required for repository edits.
- **Role** means Supervisor, Planner, Worker, Reviewer, or Researcher assignment. A proposal can request a role or permission, but deterministic policy decides whether that selection can run. New tasks snapshot manual choices so later settings edits do not silently change in-flight work.

Provider requests have bounded input and output sizes, timeouts, per-provider and per-task request limits, exact-model validation, and role effort validation. Remote providers require explicit context-sharing settings and finite request budgets; metered services also require explicit spend consent. Secrets are owner-only references into private state files, never settings values. Redirects are refused and HTTP response bodies are not passed through provider errors. Configuring an endpoint or reference does not verify authentication, entitlement, or billing.

The Supervisor accepts only the strict `answer`, `report`, `coding`, `research`, `lookup`, and `clarify` proposal intents. Its decision object also bounds one context-file read, evidence count, permissions, capabilities, and estimated calls. A strict raw JSON object or one exact JSON fence is accepted; surrounding prose, non-object JSON, unknown fields, and invalid enums are rejected. Invalid labels such as `planned_work` remain invalid. Fencing is an output-format normalization, not a routing or permission relaxation.

Repository workers use isolated task worktrees and the configured deterministic verifier. A separate Reviewer receives the current diff and verifier receipt through a read-only harness. Blocking findings feed the next bounded worker iteration. The loop records receipts and review cycles, detects unchanged repeated failures, and uses one execution deadline for worker, verifier, and review calls. A passing verifier alone cannot override a blocking review or owner-review policy.

PR preparation is local and requires a current passing receipt whose worktree hashes still match. The changed-path scanner supports tracked deletions and rejects private paths, symlinks, oversized files, and credential-like content. Commit, push, and PR creation are separate owner actions by default. Automatic delivery only runs for the explicit policy combination `automatic_pr_after_verification=true`, `require_commit_approval=false`, and `require_push_approval=false`. Actions recheck the prepared revision and hash, journal intent before side effects, and reconcile remote state after ambiguous outcomes. The PR task records the confirmed URL and stays in review; merge and deploy are unavailable.

## Focused regression artifacts

`tests/test_syntropic_orchestrator.py` reuses the disposable `test_app.PilotTests` fixture and adds deterministic HTTP protocol fixtures, no-inference Supervisor contract checks, a fake CLI worker/reviewer repair loop over real task worktrees, verified same-conversation report-context projection, atomic-claim/two-worker coverage, and local bare-remote/mock-GitHub delivery cases. `tests/test_routing_eval.py` checks strict benchmark scoring and unresolved-context labels. The final check ledger below records the guarded regression outcome.

The Explorer evidence fixture is preserved under `benchmarks/fixtures/explorer/`. Its specification was copied unchanged with SHA-256 `c9390d7d34abe9b177df4ea6800645f40c0cef4bde9caf5f995a2384503b2aa6`. The directory keeps the buggy starter and original independent verifier; `accepted-native-baseline.patch` preserves the actual fixed-native baseline patch. Run `python3 reproduce_acceptance.py` there to apply that patch in a temporary copy and replay the six cases without inference.

`benchmarks/routing_eval.py` runs deterministically by default and prints independently labeled English and Thai cases, strict intent scoring, context-resolution and role checks, difficulty error, failures, latency, and observed provider usage. It also reports fixed-native and hybrid **decision plans** only; it sets task quality and completion metrics to `null`. It never runs a worker or native CLI. Optional model routing requires `--run-ai`, explicit `--config` and disposable `--state`, `--ai-call-budget`, and is limited to a configured API Supervisor using `empero-ai/Qwen3.8-9B-Distill`. Do not point it at production state. There is no benchmark flag that executes native inference.

Example deterministic invocation:

```sh
python3 benchmarks/routing_eval.py > routing-eval.json
```

Optional bounded Qwen routing replay:

```sh
python3 benchmarks/routing_eval.py --run-ai --config /path/to/disposable/config.json \
  --state /path/to/disposable/state --ai-call-budget 8 --ai-max-cases 4
```

## Operator configuration and permissions

Configure `providers` and `roles` in `config.json` for bootstrap defaults, or use **Settings → AI providers and role assignments** for persisted owner policy. Choose an adapter that matches the endpoint protocol and exact model ID. OpenAI-compatible chat endpoints use `/v1` as the base URL; OpenAI Responses and Anthropic Messages use their own adapters. Ollama and LM Studio are restricted to loopback endpoints. A non-loopback HTTP endpoint is refused; remote services require HTTPS.

For API roles, declare reasoning efforts against the exact model ID and select only a declared effort. OpenAI-compatible `reasoning_effort` is sent only when the endpoint is explicitly declared to support it. Sampling controls are validated and applied to compatible chat/Ollama adapters; transport-specific unsupported options are not invented. For a remote service, the owner must explicitly permit context sharing, configure a finite per-provider budget, and consent to metered use when applicable.

Workers cannot use an inference-only API as a file-writing harness. Native role selections require an installed supported harness, exact configured model, permitted reasoning effort, and remaining native call budget. The task still has repository allowlist, sandbox, verifier, wall-clock, iteration, Reviewer, and owner gates. The maximum concurrent independent worker count is two; default is one.

For local PR-only preparation, leave the delivery defaults enabled. Each owner action rechecks the patch. An owner who deliberately wants automatic commit/push/PR after verification must explicitly disable the separate commit and push approval requirements and enable automatic PR creation for that named repository. This authorizes only those repository actions; task-specific instructions prohibiting commit, push, or publication still block automatic delivery. It does not authorize merging or deploying. GitHub PR URLs are stored only after `gh` readback confirms them. If the response is ambiguous, inspect the journal and reconcile remote state instead of retrying blindly.


## Recorded acceptance outcomes (2026-11-20, isolated development state)

The following supersedes provisional observations above. Tests used `/tmp/syntropic-provider-acceptance`, not installed production state. Application changes were not committed, pushed, installed as services, merged, or deployed.

| Test | Evidence and outcome | Limit |
| --- | --- | --- |
| A: simple local answer | Qwen answered 17+25 correctly through the application in 14.924 s; two local calls, no durable job or native calls. | One simple question, not a general accuracy result. |
| B: context follow-up | After the receipt-context fix, Qwen produced a grounded report in 28.981 s: `explorer.py`, six cases, verified result, no confirmed commit/push. Zero added native calls. | Earlier attempt failed HTTP 503 and is retained. Visible retry omitted revision and explicit absent PR URL, although both were in canonical context. |
| C: difficulty/context | English Explorer proposal selected coding, difficulty 3, and inspected SPEC.md in one bounded context round; file hash matched. | Model strategy varied between proposals; no claim of calibrated difficulty. |
| D: planner selection | Role selection and explicit model/effort bindings have deterministic coverage. | Actual complex Qwen proposals failed bounds/invalid intent. No successful live complex planner execution is claimed. |
| E: worker/reviewer | Real Luna Medium Worker plus distinct read-only Luna Medium Reviewer passed the independent six-case verifier. Deterministic fake-CLI regression also exercises reviewer finding a real missing fallback, worker correction, and independent postcheck. | The real Reviewer approved its first patch; the corrective iteration demonstration is deterministic, not an additional paid model run. |
| F: recovery | Regression coverage includes interruption/recovery, stale revision, cancellation, budget exhaustion, repeated unchanged failure, and failing verifier overriding review approval. | See final check ledger for pass counts. |
| G: PR | Real verified task prepared patch/body/metadata and entered InReview; separate authenticated fixture acceptance moved it to Done for UI inspection. Local bare-remote/fake-gh tests cover separate delivery actions, preauthorization, and ambiguous result reconciliation. | No real GitHub PR, commit, push, merge, or deployment from this application change. |
| H: settings | Nine browser checks pass, including provider/model persistence across reload. Deterministic tests cover role snapshot/effort, exclusions, and transport selection. | Live authentication and entitlements for additional commercial providers were not tested. |
| I: disconnect | HTTP request disconnected before durable worker start; execution completed independently. Browser reconnect/history replay passed. | Dedicated browser-offline probe arrived after InReview; it does not prove a browser disconnected during active execution. |
| J: comparison | Fixed-native and hybrid Explorer executions both pass the same independent six cases. Separate routing replay labels and strict failures are retained. | Small sample; decision-plan replay does not measure task completion or prove hybrid superiority. |

### Execution and resource evidence

Fixed-native Luna Medium baseline: 45.519 s, six cases passed. Hybrid was split: initial Qwen routing 42.204 s, then preflight stopped before native execution because the disposable verifier executable was relative. After correcting the test configuration and an explicit same-task follow-up, Worker→verifier→Reviewer→prepared result took 45.112 s. These are separate measured phases, not one uninterrupted end-to-end latency.

Only three native test executions were used against the root's cap of four: one baseline and two application calls (Worker and Reviewer). No additional native inference was used for the context report. Model/effort contexts are recorded in `evidence/provider-orchestrator/observed-native-models.json`: implementation workers use Luna Max, application/baseline inference uses Luna Medium; one Sol 6.1 Medium planner and one final reviewer were used. The final review identified five security/budget issues; fixes and deterministic regression checks followed, without another AI review.

Sampled hybrid child-process metrics: Worker 33.882 s / peak RSS 164,659,200 B / CPU 0.51 s; Reviewer 10.229 s / peak RSS 161,628,160 B / CPU 0.37 s; verifier 0.284 s / peak RSS 2,342,912 B. These exclude provider-side compute, shared model-server memory, GPU allocation, and between-sample peaks. GPU memory is unavailable, not zero. Qwen health check sampled server RSS 5,534,842,880 B; its CPU observation includes process startup/lifetime and is not request-delta CPU.

### Downloaded model and reproduction

Original Hugging Face repository: `empero-ai/Qwen3.8-9B-Distill`, pinned revision `0934f3d2327ff2df2197495278c4c46ae5a56bd9`. Original safetensors (19,306,305,296 B) matched SHA-256 `90d46f174c3cfc0d29a782f49402d7474f46c035df29afd0c815240427f6f062` and remain under `~/Downloads/SyntropicModels/Qwen3.8-9B-Distill`.

Actual local inference used its official-MLX affine 4-bit/group-64 derivative under `~/Downloads/SyntropicModels/MLX/empero-ai/Qwen3.8-9B-Distill` (about 5.06 GB), served with the exact registered ID. Results do not represent original BF16 precision. Source/derived provenance is in `qwen-source.json`; no arbitrary remote model code was trusted.

For a similar local setup, run an OpenAI-compatible local endpoint with that exact registered model ID, then adapt `config.qwen-luna.acceptance.example.json` to the endpoint and allowed repository. Configure Supervisor to that API provider and Worker/Reviewer to the installed native harness with declared model and permitted effort. The example is a disposable acceptance configuration, not a production installation command. Additional providers require the matching transport, exact model IDs, supported efforts, finite budgets, and owner-only secret references; remote context sharing and metered spending require explicit settings.

Primary implementation files are `providers.py`, `supervisor.py`, `output_safety.py`, `control.py`, `app.py`, `workflows.py`, `services.py`, `pr_delivery.py`, `ops.py`, `frontend/src/AgentSettings.tsx`, `frontend/src/main.tsx`, and `frontend/src/api.ts`. Regression and reproduction files live under `tests/` and `benchmarks/`. The working tree also contains earlier task changes; this list does not claim every uncommitted file originated in this stage.


### Routing comparison outcome

The bounded optional Qwen replay used four local calls (3,318 input / 974 output tokens), mean routing latency 17,568.286 ms. Two of four intents matched the independent labels; three responses were valid decisions and one Thai response failed the strict capability/permission/evidence contract. The no-context report case proposed a report despite having no verified prior task; it scored incorrect. No label normalization or worker execution was used to improve the score. Difficulty mean absolute error was 1.667 on valid returned decisions.

The deterministic heuristic replay matched 13/13 intent labels, 10/13 exact role plans, and 10/13 context-resolution labels; mean routing latency was about 0.13 ms in the paired run. On the same first four cases its intent accuracy was 4/4 versus Qwen 2/4. Fixed-native and hybrid policy rows are replayed decision plans with completion metrics null; their separate real Explorer execution results are described above. This small fixture set is not a representative population and does not establish production accuracy, cost savings, or superiority of any router.


### Restarting the downloaded local model manually

The development model server was stopped after testing to free memory. No production service was installed. While the temporary development environment exists, restart it from a terminal with:

```sh
cd /Users/manpao/Downloads/SyntropicModels/MLX
/tmp/syntropic-qwen-env/bin/python -m mlx_lm server \
  --model empero-ai/Qwen3.8-9B-Distill --host 127.0.0.1 --port 8791 \
  --temp 0.6 --top-p 0.95 --top-k 20 --max-tokens 2048 \
  --chat-template-args '{"enable_thinking":false}' \
  --prefill-step-size 128 --decode-concurrency 1 --prompt-concurrency 1 \
  --prompt-cache-size 2 --prompt-cache-bytes 536870912
```

Use base URL `http://127.0.0.1:8791/v1` and the exact model ID above in provider settings. The working directory preserves that relative model ID. `/tmp/syntropic-qwen-env` is a development environment and may be removed by system cleanup; the downloaded weights in Downloads remain separate. The app's own preview server was also stopped after verification. Its existing installed production service was not restarted or changed.


## Final check ledger

| Check | Final outcome |
| --- | --- |
| Guarded full Python suite | **91 passed**, zero failures/errors, 100.513 s. Zero attempted live-model POSTs. |
| Strict TypeScript and Vite production build | Passed. Existing large-chunk advisory remains in build output. |
| Component/security rendering checks | **4 passed**. |
| Playwright real disposable app | **9 passed**, zero skipped/failed, 13.3 s. Includes first-allowlisted non-demo repository selection. |
| Independent Explorer fixture reproduction | **6 cases passed**; original SPEC and verifier hashes unchanged. |
| Staged runtime module import | Passed, including all newly introduced modules in the packaging copy list; no installation. |
| Tracked whitespace/diff check | Passed. |

The last fixture corrections removed a deliberately invalid provider from test configuration after its rejection assertion, and kept the no-publication task in Review because its explicit owner-review policy requires it. The final full-suite result includes both corrections. No additional AI review was run.

Sanitized evidence is exported under `evidence/provider-orchestrator/sanitized/`, with SHA-256 manifest and source hashes. It includes final check logs, model provenance, routing results, receipt/resource metadata, and declared limitations. Raw native sessions, private reasoning, credential references, and raw model output traces are omitted. Development screenshots are `settings-loaded-desktop.png`, `settings-loaded-mobile.png`, and `task-inspector-loaded.png`; the loaded mobile settings document and viewport are both 390 px wide. Evidence and downloaded weights remain local; the ignored evidence directory is not automatically included in a future Git commit.

Remaining blockers are model reliability for complex/Thai routing, absence of live credential/entitlement checks for other providers, and no real GitHub publication. The running-window browser-offline check is partial as described above. Treat automatic routing/delivery as configuration that still needs representative owner validation before production use.
