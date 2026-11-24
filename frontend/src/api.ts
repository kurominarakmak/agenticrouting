export interface Task {
  id: string;
  title: string;
  body: string;
  status: string;
  column: string;
  activity: string;
  conversation: string;
  parent_id: string | null;
  started_at?: number | null;
  completed_at?: number | null;
  approval: string;
  revision: number;
  attempts: number;
  error: string;
  route: Record<string, any> & { runtime?: string; decision_source?: string; supervisor_decision?: Record<string, any>; assignments?: Record<string, any> };
  delivery?: PreparedDelivery | null;
  plan: unknown;
  dependencies: string[];
  artifacts: string[];
  runs: unknown[];
  comments: { created_at: number; author: string; body: string }[];
}
export interface ProviderSpec {
  type: "ollama" | "lmstudio" | "openai-compatible" | "openai" | "anthropic";
  base_url: string;
  label?: string;
  enabled?: boolean;
  remote?: boolean;
  share_context?: boolean;
  metered?: boolean;
  consent?: boolean;
  budget_calls?: number;
  task_call_limit?: number;
  max_output_tokens?: number;
  timeout_seconds?: number;
  secret_ref?: string;
  credential_configured?: boolean;
  models?: string[];
  structured_output?: boolean;
  capabilities?: string[];
  harnesses?: string[];
  api_version?: string;
  temperature?: number;
  top_p?: number;
  reasoning_parameter?: string;
  reasoning_efforts_by_model?: Record<string, string[]>;
}
export interface RoleSpec {
  mode?: "auto" | "manual";
  enabled?: boolean;
  backend?: "api" | "native" | "dsh";
  provider?: string;
  model?: string;
  runtime?: string;
  reasoning_effort?: string;
}
export interface OrchestrationSettings {
  providers: Record<string, ProviderSpec>;
  roles: Record<string, RoleSpec>;
  policy: { max_iterations: number; max_concurrency: number; max_provider_calls_per_task: number; max_native_calls_per_task: number; native_call_budget: number; max_wall_seconds: number };
  provider_priority: string[];
  excluded_providers: string[];
  pr_policy: Record<string, { require_commit_approval: boolean; require_push_approval: boolean; automatic_pr_after_verification: boolean; require_owner_review_before_done: boolean }>;
}
export interface PreparedDelivery {
  revision: number;
  branch: string;
  title: string;
  body_path: string;
  patch_path: string;
  patch_sha256: string;
  publish_allowed: number | boolean;
  status: string;
  commit_sha?: string | null;
  pushed_at?: number | null;
  pr_url?: string | null;
  review_task_id?: string | null;
  policy: OrchestrationSettings["pr_policy"][string];
}
export interface AgentCall {
  id: number;
  task_id: string;
  role: string;
  provider: string;
  model: string;
  created: number;
}
export interface Message {
  id: number;
  created: number;
  role: string;
  text: string;
  meta: string;
  task_id?: string;
}
export interface Runtime {
  id: string;
  name: string;
  harness: string;
  available: boolean;
  authentication?: string;
  capabilities: string[];
  quota: string;
}
export interface ProviderModel {
  id: string;
  name: string;
  provider: string;
  provider_type: string;
  base_url: string;
  remote: boolean;
  enabled: boolean;
  available: boolean | null;
  discovery: string;
  availability: "observed" | "unavailable" | "unknown";
  models: { id: string; source: "endpoint" | "configuration" }[];
  authentication: string;
  billing: string;
  budget_calls?: number | null;
  task_call_limit: number;
  quota: string;
}
export interface Snapshot {
  tasks: Task[];
  task_total: number;
  conversation_total: number;
  conversations: { id: string; title: string }[];
  conversation?: string;
  messages: Message[];
  agent_calls?: AgentCall[];
  worker: { online: boolean };
  resources: { repositories: string[] };
  // Provider-neutral AI adapters are distinct from execution harnesses.
  registry: { runtimes: Runtime[]; providers?: ProviderModel[] };
  settings: {
    routing: string;
    review_before_done: boolean;
    notifications: boolean;
    orchestration?: OrchestrationSettings;
  };
  notifications: { id: number; kind: string; text: string; task_id?: string }[];
  knowledge: {
    roots: { id: string; path: string; share_frontier: boolean }[];
    sources: unknown[];
    memories: { kind: string; text: string; frontier: boolean }[];
  };
  tools: {
    name: string;
    enabled: boolean;
    transport: string;
    allowed_tools: string[];
  }[];
  routing_history: unknown[];
}
export async function api<T>(
  token: string,
  path: string,
  data?: unknown,
): Promise<T> {
  const r = await fetch(path, {
    method: data === undefined ? "GET" : "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(data === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const value = r.headers.get("content-type")?.includes("json")
    ? await r.json()
    : await r.text();
  if (!r.ok)
    throw Error(typeof value === "object" ? value.error : "Request failed");
  return value as T;
}
export type StreamEvent =
  | { type: "delta"; text: string }
  | { type: "result"; data: { conversation: string } }
  | { type: "error"; error: string }
  | { type: "heartbeat" };
export async function stream(
  token: string,
  data: unknown,
  onEvent: (e: StreamEvent) => void,
) {
  const r = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw Error((await r.json()).error);
  if (!r.body) throw Error("Streaming is unavailable");
  const reader = r.body.getReader(),
    decoder = new TextDecoder();
  let pending = "";
  const consume = (line: string) => {
    if (line.trim()) onEvent(JSON.parse(line) as StreamEvent);
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      let at;
      while ((at = pending.indexOf("\n")) >= 0) {
        consume(pending.slice(0, at));
        pending = pending.slice(at + 1);
      }
      if (done) {
        consume(pending);
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
}
