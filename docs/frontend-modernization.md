# React frontend modernization

## Architecture and scope

React 18 + strict TypeScript + Vite build to static files. Python serves the build at `/ui/` and, when present, at `/`. The original UI remains at `/legacy/`, or at `/` if no build exists. There is no Node server in production. The existing Python/Hermes database, worker, official harness adapters, verification, worktrees and authentication remain authoritative.

Changes: `frontend/` adds API contracts, NDJSON streaming, React views, controlled renderers, DSH Button and tests; `app.py` adds bounded static serving and two classification refinements; `ops.py` copies a prebuilt frontend during an explicitly requested install. No service installation, database migration, commit, push or publication was performed for this change. A separate local development HTTP server on port 8788 reads the existing application state and uses its existing APIs; existing services stay on 8787.

## DeepSeek Harness investigation

Inspected upstream at `39163dd30f703a79079e2d2446545cff3c453738`: root license, Web frontend package, UI primitives package and exports, Button/CSS, AssistantMarkdown, MarkdownText pipeline, FileDiff, and chat plugin dependencies. MIT attribution is retained in `frontend/THIRD_PARTY_NOTICES.md` and `frontend/src/vendor/DSH-LICENSE`.

| Candidate | Decision | Concrete reason |
|---|---|---|
| DSH Web shell as foundation (A) | Rejected for this implementation | Its Web entry loads DSH client modules, Cordis, connection/session controllers and workspace services. A Syntropic bridge must supply those contracts while avoiding a second authoritative session store. No demonstrated reduction in custom integration code |
| Syntropic React with selective primitives (B) | Selected | Two real-data slices work directly against current APIs: streamed Chat and full task inspector with existing artifacts/receipts/controls. Preserves backend behavior and static hosting |
| DSH Button | Reused unchanged, pinned source | Pure React/clsx/CSS module with native attributes and refs; minimal dependency surface |
| DSH AssistantMarkdown/chat | Rejected | Requires render slots, presentation/disclosure hooks, DSH AssistantBlock snapshot contracts and localized session ownership |
| DSH MarkdownText | Rejected for source copying | Standalone atom entry is backed by its own incremental parser/render pipeline, Shiki and workspace-path helpers. Copying the whole dependency graph adds maintenance; public package is a prerelease with a Cordis workspace peer |
| DSH FileDiff | Rejected | Consumes WorkspaceDiffHunk, ChangesDiffState, locale slots and DSH highlighter. Current API supplies unified patch text; controlled line rendering is sufficient |
| DSH approval/tool/session UI | Rejected | Existing approval revision fencing and permission endpoints must remain authoritative; DSH controllers do not directly implement those contracts |
| DSH agent runtime | Not adopted | UI reuse does not establish native subscription execution, ownership/restart semantics, or a maintenance advantage over the verified worker |

A complete DSH Web foundation was not installed or benchmarked. These decisions rely on inspected dependency contracts and two working B integration slices, not a measured head-to-head DSH Web performance claim. DSH describes itself as a rapidly changing developer preview. Reassess package adoption when stable public contracts materially reduce integration code.

## UI behavior

All five views use backend snapshots and mutation APIs. Task status, routing, approvals, worktree artifacts, revisions and verification receipts are backend records. Task buttons use native keyboard behavior; native modal dialogs trap focus and support Escape. The sidebar is hidden from the mobile accessibility tree when closed. Markdown, GFM tables, mathematics, highlighted code and unified diffs render through controlled React components. Raw HTML, script URLs and remote Markdown images are excluded. The schema registry accepts bounded typed tables and numeric charts, terminal/diff text and Markdown; unsupported data remains an inspectable reference object. Rich-rendering code loads separately from the application shell.

Generative visuals remain deliberately modest: there is no unrestricted model HTML/JavaScript executor, automatic arbitrary tool executor or general diagram language runtime. Source provenance and research/tool records are inspectable structured data. Browser notifications require explicit browser permission. Existing durable inbox/outbox behavior stays in Python.

## Verification and measurements

- Baseline: 47 Python tests passed in 61.611 s.
- Backend after initial frontend integration: 47 passed in 50.614 s. Final run: **48 tests passed in 55.618 s**, including static serving and traversal rejection.
- Four component checks passed: native DSH Button attributes, untrusted Markdown, tables/math/highlighting, and numeric-only response rendering.
- Real browser: deterministic streamed dog answer and actual Ollama arithmetic persisted through the source preview. Task inspector showed real Codex/Ollama work, local handoffs, receipt, logs and unified greeting patch.
- Four Playwright tests passed (11.7 s), including the idle comparison: real API task count agreement, inspector and Escape, deterministic stream persistence without task creation, 390 × 844 navigation and page width, and an idle comparison. Real provider accounts were not invoked by the automated tests.
- Build: strict TypeScript passes. App shell approximately 164 KB minified / 53 KB gzip; rich Markdown/math/highlighting approximately 620 KB / 186 KB gzip. Final values are recorded in local build output. The rich chunk exceeds Vite's 500 KB advisory threshold; it is lazy loaded, not hidden by changing the warning limit.
- Initial single Chromium idle sample: legacy heap 2,569,932 bytes; React heap 2,892,480 bytes. Five-second main-thread work: 10.751 ms vs 13.634 ms. This is not a statistical CPU/RSS benchmark or a result for DSH Web. Both clients poll the same API every 2.5 seconds. No backend rewrite or performance improvement is claimed.
- Routing: 11 explicit labeled requests pass, versus 5/11 always-chat and 5/11 always-job baselines. No inference is invoked. The set specifically checks request prefixes and explanatory questions; it is not evidence of general model-selection quality.

No new physical iPhone, Safari engine, remote network, Claude, GLM or external MCP account verification is claimed. Existing disconnected-client, follow-up, approval and subscription safety regressions remain in the Python suite. Broader accessibility auditing, statistically repeated resource measurements, DSH Web foundation benchmarks and richer research diagrams remain limitations.

## Run and review

```sh
cd /path/to/agenticrouting/frontend
npm ci
npm run build
npm run test:components
npx playwright install chromium
npm test
```

Browser integration tests expect the authenticated development service at `http://127.0.0.1:8788` and read the existing owner-only token file locally; they do not print or commit it. They add harmless chat messages to history. Set `SYNTROPIC_TOKEN_FILE` for another token file. The default live service is not restarted by frontend tests.

For UI development against an existing loopback backend on 8787, run `npm run dev`, then open `http://127.0.0.1:5173/ui/`. The Vite proxy forwards only the known development origin to the backend's loopback origin; the production Host/Origin checks remain intact. Node is required for building/development only.

The current preview is `http://127.0.0.1:8788/ui/`. After reviewing and authorizing installation, build first and run the normal `python3 ops.py install`; this replaces only this application's installed files and preserves live state. No installation was run during this task.
