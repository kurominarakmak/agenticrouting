import { useEffect, useMemo, useState } from "react";
import { Button } from "./vendor/Button";
import type { OrchestrationSettings, ProviderModel, ProviderSpec, RoleSpec, Runtime } from "./api";

const roles = ["supervisor", "planner", "worker", "reviewer", "researcher"] as const;
const runtimeChoices = ["codex-chatgpt", "claude-subscription", "glm-coding-plan", "dsh-local"];
const defaults = (): OrchestrationSettings => ({
  providers: {}, roles: Object.fromEntries(roles.map((role) => [role, { mode: "auto", enabled: role === "supervisor" || role === "worker" }])),
  policy: { max_iterations: 2, max_concurrency: 1, max_provider_calls_per_task: 8, max_native_calls_per_task: 4, native_call_budget: 0, max_wall_seconds: 300 },
  provider_priority: [], excluded_providers: [], pr_policy: {},
});
type Props = { value?: OrchestrationSettings; inventory: ProviderModel[]; runtimes: Runtime[]; repositories: string[]; save: (value: OrchestrationSettings) => Promise<unknown>; refreshModels: () => Promise<void> };
const csv = (value: string) => value.split(",").map((x) => x.trim()).filter(Boolean);

export function AgentSettings({ value, inventory, runtimes, repositories, save, refreshModels }: Props) {
  const source = useMemo(() => JSON.stringify(value || defaults()), [value]);
  const [draft, setDraft] = useState<OrchestrationSettings>(() => value || defaults());
  const [newId, setNewId] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { setDraft(JSON.parse(source) as OrchestrationSettings); }, [source]);
  const updateProvider = (id: string, patch: Partial<ProviderSpec>) => setDraft((old) => ({ ...old, providers: { ...old.providers, [id]: { ...old.providers[id], ...patch } as ProviderSpec } }));
  const updateRole = (role: string, patch: Partial<RoleSpec>) => setDraft((old) => ({ ...old, roles: { ...old.roles, [role]: { ...old.roles[role], ...patch } } }));
  const updatePolicy = (key: keyof OrchestrationSettings["policy"], value: number) => setDraft((old) => ({ ...old, policy: { ...old.policy, [key]: value } }));
  async function persist() {
    setSaving(true);
    try {
      const providers = Object.fromEntries(Object.entries(draft.providers).map(([id, spec]) => {
        const { credential_configured: _hidden, ...safe } = spec;
        return [id, safe];
      }));
      await save({ ...draft, providers });
    } finally { setSaving(false); }
  }
  function addProvider() {
    const id = newId.trim();
    if (!/^[A-Za-z0-9_.-]{1,64}$/.test(id) || draft.providers[id]) return;
    setDraft((old) => ({ ...old, providers: { ...old.providers, [id]: { type: "openai-compatible", base_url: "http://127.0.0.1:1234/v1", enabled: false, remote: false, models: [], task_call_limit: 8, max_output_tokens: 1200 } } }));
    setNewId("");
  }
  return <section className="agent-settings" aria-label="AI provider and agent settings">
    <h2>AI providers and role assignments</h2>
    <p className="subtle">Provider APIs can propose and review work. Repository edits run through a selected native coding harness. Remote context and metered spend require explicit consent. No automatic paid fallback is used.</p>
    <div className="card">
      <h3>Provider adapters</h3>
      <p className="subtle">Model IDs must be configured exactly or observed through discovery. Secret values never belong here; enter an owner-only reference such as <code>provider.json#API_KEY</code>.</p>
      {Object.entries(draft.providers).map(([id, spec]) => {
        const found = inventory.find((x) => x.id === id);
        const models = spec.models || [];
        const reasonByModel = spec.reasoning_efforts_by_model || {};
        return <article className="card provider-editor" key={id}>
          <div className="settings-row"><strong>{id}</strong><span className="badge">{found?.availability || "not probed"}</span><label><input type="checkbox" checked={!!spec.enabled} onChange={(e) => updateProvider(id, { enabled: e.target.checked })}/> Enabled</label></div>
          <label>Adapter <select aria-label={`${id} adapter`} value={spec.type} onChange={(e) => updateProvider(id, { type: e.target.value as ProviderSpec["type"] })}>{["ollama", "lmstudio", "openai-compatible", "openai", "anthropic"].map((x) => <option key={x}>{x}</option>)}</select></label>
          <label>Base URL <input aria-label={`${id} base URL`} value={spec.base_url} onChange={(e) => updateProvider(id, { base_url: e.target.value })}/></label>
          <label>Exact model IDs <input aria-label={`${id} model IDs`} value={models.join(", ")} onChange={(e) => updateProvider(id, { models: csv(e.target.value) })} placeholder="model id, another exact id"/></label>
          <div className="settings-grid">
            <label>Call cap per task <input type="number" min={1} max={100} value={spec.task_call_limit ?? 8} onChange={(e) => updateProvider(id, { task_call_limit: Number(e.target.value) })}/></label>
            <label>Max output tokens <input type="number" min={1} max={8192} value={spec.max_output_tokens ?? 1200} onChange={(e) => updateProvider(id, { max_output_tokens: Number(e.target.value) })}/></label>
            <label>Temperature <input type="number" min={0} max={2} step={0.05} value={spec.temperature ?? 0} onChange={(e) => updateProvider(id, { temperature: Number(e.target.value) })}/></label>
            <label>Top p <input type="number" min={0} max={1} step={0.05} value={spec.top_p ?? 1} onChange={(e) => updateProvider(id, { top_p: Number(e.target.value) })}/></label>
            {spec.remote && <label>Provider request budget <input type="number" min={1} value={spec.budget_calls ?? 1} onChange={(e) => updateProvider(id, { budget_calls: Number(e.target.value) })}/></label>}
            <label>Owner secret reference <input aria-label={`${id} owner secret reference`} value={spec.secret_ref || ""} placeholder={spec.credential_configured ? "configured; leave blank to keep" : "filename#KEY"} onChange={(e) => updateProvider(id, { secret_ref: e.target.value || undefined })}/></label>
          </div>
          <label><input type="checkbox" checked={!!spec.remote} onChange={(e) => updateProvider(id, { remote: e.target.checked, ...(e.target.checked ? {} : { share_context: false, metered: false, consent: false }) })}/> Remote provider (HTTPS required)</label>
          {spec.remote && <div className="settings-grid">
            <label><input type="checkbox" checked={!!spec.share_context} onChange={(e) => updateProvider(id, { share_context: e.target.checked })}/> Allow scoped private context sharing</label>
            <label><input type="checkbox" checked={!!spec.metered} onChange={(e) => updateProvider(id, { metered: e.target.checked, ...(e.target.checked ? {} : { consent: false }) })}/> Metered billing</label>
            <label><input type="checkbox" checked={!!spec.consent} onChange={(e) => updateProvider(id, { consent: e.target.checked })}/> Confirm spend consent</label>
          </div>}
          {spec.type === "openai-compatible" && <label>Reasoning parameter <select value={spec.reasoning_parameter || ""} onChange={(e) => updateProvider(id, { reasoning_parameter: e.target.value || undefined })}><option value="">Unsupported / none</option><option value="reasoning_effort">reasoning_effort</option></select></label>}
          <label>Reasoning efforts for selected model <input aria-label={`${id} reasoning efforts`} value={(reasonByModel[models[0]] || []).join(", ")} onChange={(e) => updateProvider(id, { reasoning_efforts_by_model: models[0] ? { ...reasonByModel, [models[0]]: csv(e.target.value) } : reasonByModel })} placeholder="low, medium, high"/></label>
          <p className="subtle">{found?.discovery || "Availability unknown until you refresh discovery."} · quota {found?.quota || "not reported"} · {found?.authentication || "authentication not verified"}</p>
        </article>;
      })}
      <div className="toolbar"><label>New provider ID <input aria-label="New provider ID" value={newId} onChange={(e) => setNewId(e.target.value)} placeholder="local-qwen"/></label><Button onClick={addProvider}>Add provider</Button><Button onClick={() => void refreshModels()}>Discover configured models</Button></div>
    </div>

    <div className="card">
      <h3>Agent roles</h3>
      {roles.map((role) => {
        const spec = draft.roles[role] || { mode: "auto", enabled: false };
        const provider = draft.providers[spec.provider || ""];
        const choices = [...new Set([...(provider?.models || []), ...inventory.find((p) => p.id === spec.provider)?.models.map((m) => m.id) || []])];
        const native = runtimes.filter((r) => runtimeChoices.includes(r.id));
        return <article className="card role-editor" key={role}>
          <div className="settings-row"><strong>{role}</strong><label><input type="checkbox" aria-label={`${role} enabled`} checked={spec.enabled ?? (role === "supervisor" || role === "worker")} onChange={(e) => updateRole(role, { enabled: e.target.checked })}/> Enabled</label></div>
          <div className="settings-grid">
            <label>Selection <select aria-label={`${role} selection`} value={spec.mode || "auto"} onChange={(e) => updateRole(role, { mode: e.target.value as RoleSpec["mode"], backend: spec.backend || (role === "worker" ? "native" : "api") })}><option value="auto">Auto</option><option value="manual">Manual</option></select></label>
            {spec.mode === "manual" && <>
              <label>Backend <select aria-label={`${role} backend`} value={spec.backend || (role === "worker" ? "native" : "api")} onChange={(e) => updateRole(role, { backend: e.target.value as RoleSpec["backend"] })}>{(role === "worker" ? ["native"] : ["api", "native", "dsh"]).map((x) => <option key={x}>{x}</option>)}</select></label>
              {spec.backend === "api" && role !== "worker" && <>
                <label>Provider <select aria-label={`${role} provider`} value={spec.provider || ""} onChange={(e) => updateRole(role, { provider: e.target.value, model: draft.providers[e.target.value]?.models?.[0] || "" })}><option value="">Choose configured provider</option>{Object.entries(draft.providers).map(([id, p]) => <option key={id} value={id} disabled={!p.enabled}>{id} · {p.type}</option>)}</select></label>
                <label>Model <input aria-label={`${role} model`} list={`${role}-models`} value={spec.model || ""} onChange={(e) => updateRole(role, { model: e.target.value })}/><datalist id={`${role}-models`}>{choices.map((m) => <option key={m} value={m}/>)}</datalist></label>
                {!!provider?.reasoning_efforts_by_model?.[spec.model || ""]?.length && <label>Reasoning effort <select aria-label={`${role} reasoning effort`} value={spec.reasoning_effort || ""} onChange={(e) => updateRole(role, { reasoning_effort: e.target.value || undefined })}><option value="">Provider default</option>{provider.reasoning_efforts_by_model[spec.model || ""].map((x) => <option key={x}>{x}</option>)}</select></label>}
              </>}
              {spec.backend === "native" && <>
                <label>Execution harness <select aria-label={`${role} harness`} value={spec.runtime || "codex-chatgpt"} onChange={(e) => updateRole(role, { runtime: e.target.value })}>{runtimeChoices.map((x) => <option key={x} value={x}>{x}{native.find((r) => r.id === x)?.available ? " · observed" : " · may be unavailable"}</option>)}</select></label>
                <label>Exact model <input aria-label={`${role} native model`} value={spec.model || ""} onChange={(e) => updateRole(role, { model: e.target.value })} placeholder="Use harness configured model"/></label>
                {spec.runtime === "codex-chatgpt" && <label>Reasoning effort <input aria-label={`${role} reasoning effort`} value={spec.reasoning_effort || ""} onChange={(e) => updateRole(role, { reasoning_effort: e.target.value })} placeholder="Use harness configured effort"/></label>}
              </>}
            </>}
          </div>
          <p className="subtle">{spec.mode === "manual" ? "This role selection is snapshotted into new tasks. Existing tasks keep their assignment." : "Auto uses configured capabilities and current privacy/budget policy."}</p>
        </article>;
      })}
    </div>

    <div className="card">
      <h3>Routing and execution limits</h3>
      <div className="settings-grid">
        {([ ["max_iterations", "Worker / review iterations", 1, 3], ["max_concurrency", "Independent tasks at once", 1, 2], ["max_provider_calls_per_task", "Provider calls per task", 1, 30], ["max_native_calls_per_task", "Native calls per task", 1, 30], ["native_call_budget", "Native calls total", 0, 100], ["max_wall_seconds", "Task wall clock seconds", 15, 3600] ] as const).map(([key, title, min, max]) => <label key={key}>{title}<input type="number" min={min} max={max} value={draft.policy[key]} onChange={(e) => updatePolicy(key, Number(e.target.value))}/></label>)}
      </div>
      <label>Provider and harness priority <input aria-label="Provider priority" value={draft.provider_priority.join(", ")} onChange={(e) => setDraft((old) => ({ ...old, provider_priority: csv(e.target.value) }))} placeholder="provider-id, codex-chatgpt"/></label>
      <label>Excluded providers or harnesses <input aria-label="Provider exclusions" value={draft.excluded_providers.join(", ")} onChange={(e) => setDraft((old) => ({ ...old, excluded_providers: csv(e.target.value) }))}/></label>
      <p className="subtle">Concurrency is limited to two independent claimed Hermes tasks, each in its own worktree. Dependencies remain sequential. No automatic paid fallback or budget increase.</p>
    </div>

    <div className="card">
      <h3>Repository delivery policy</h3>
      <p className="subtle">A verified patch and PR description are prepared locally. Commit, push, and PR creation need separate owner approval by default. An explicit policy can preauthorize all three after verification. Merge and deploy are unavailable.</p>
      {repositories.map((repo) => {
        const policy = Object.assign({ require_commit_approval: true, require_push_approval: true, automatic_pr_after_verification: false, require_owner_review_before_done: true }, draft.pr_policy[repo]);
        return <fieldset className="card pr-policy" key={repo}><legend>{repo}</legend>
          {Object.entries({ require_commit_approval: "Require owner approval for local commit", require_push_approval: "Require owner approval for push", automatic_pr_after_verification: "Request automatic PR creation after verification", require_owner_review_before_done: "Keep verified task in review until owner accepts" }).map(([key, title]) => <label key={key}><input type="checkbox" checked={policy[key as keyof typeof policy]} onChange={(e) => setDraft((old) => ({ ...old, pr_policy: { ...old.pr_policy, [repo]: { ...policy, [key]: e.target.checked } } }))}/>{title}</label>)}
        </fieldset>;
      })}
    </div>
    <Button disabled={saving} onClick={() => void persist()}>{saving ? "Saving…" : "Save provider and orchestration settings"}</Button>
  </section>;
}
