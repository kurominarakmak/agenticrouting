export interface Task {
  id: string;
  title: string;
  body: string;
  status: string;
  column: string;
  activity: string;
  conversation: string;
  parent_id: string | null;
  approval: string;
  revision: number;
  attempts: number;
  error: string;
  route: { runtime?: string };
  plan: unknown;
  dependencies: string[];
  artifacts: string[];
  runs: unknown[];
  comments: { created_at: number; author: string; body: string }[];
}
export interface Message {
  id: number;
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
export interface Snapshot {
  tasks: Task[];
  task_total: number;
  conversation_total: number;
  conversations: { id: string; title: string }[];
  messages: Message[];
  worker: { online: boolean };
  resources: { repositories: string[] };
  registry: { runtimes: Runtime[] };
  settings: {
    routing: string;
    review_before_done: boolean;
    notifications: boolean;
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
