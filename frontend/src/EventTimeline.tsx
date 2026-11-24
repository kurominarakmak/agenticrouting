import { useEffect, useState } from "react";
import { api } from "./api";
interface AgentEvent {
  cursor: number;
  task_id: string;
  revision: number;
  execution_id: string;
  sequence: number;
  timestamp: number;
  runtime: string;
  model: string;
  event_type: string;
  payload: Record<string, unknown>;
}
interface Replay {
  events: AgentEvent[];
  cursor: number;
  revision: number;
  has_more: boolean;
}
export function EventTimeline({
  task,
  revision,
  token,
}: {
  task: string;
  revision: number;
  token: string;
}) {
  const [events, setEvents] = useState<AgentEvent[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true,
      cursor = 0;
    const abort = new AbortController();
    setEvents([]);
    setError("");
    const accept = (event: AgentEvent) => {
      if (
        event.task_id !== task ||
        event.revision !== revision ||
        !Number.isSafeInteger(event.cursor) ||
        event.cursor <= cursor
      )
        return;
      cursor = event.cursor;
      setEvents((old) => [...old, event].slice(-5000));
    };
    const follow = async () => {
      try {
        let more = true;
        while (active && more) {
          const page = await api<Replay>(
            token,
            `/api/events?task=${encodeURIComponent(task)}&revision=${revision}&after=${cursor}`,
          );
          if (!active) return;
          if (page.revision !== revision) throw Error("Stale task revision");
          for (const e of page.events) accept(e);
          more = page.has_more;
        }
        while (active) {
          const response = await fetch(
            `/api/events/stream?task=${encodeURIComponent(task)}&revision=${revision}&after=${cursor}`,
            {
              headers: { Authorization: `Bearer ${token}` },
              signal: abort.signal,
            },
          );
          if (!response.ok || !response.body)
            throw Error("Timeline connection interrupted; replay will resume");
          const reader = response.body.getReader(),
            decoder = new TextDecoder();
          let pending = "";
          setError("");
          try {
            while (active) {
              const { value, done } = await reader.read();
              if (done) break;
              pending += decoder.decode(value, { stream: true });
              let at;
              while ((at = pending.indexOf("\n\n")) >= 0) {
                const packet = pending.slice(0, at);
                pending = pending.slice(at + 2);
                if (packet.includes("event: reset"))
                  throw Error("Task revision changed; reload state");
                const data = packet
                  .split("\n")
                  .find((l) => l.startsWith("data: "));
                if (data) accept(JSON.parse(data.slice(6)) as AgentEvent);
              }
            }
          } finally {
            reader.releaseLock();
          }
        }
      } catch (e) {
        if (active) setError(String(e));
      }
    };
    let retry: ReturnType<typeof setInterval> | undefined;
    let running = false;
    const run = async () => {
      if (running) return;
      running = true;
      try {
        await follow();
      } finally {
        running = false;
      }
    };
    void run();
    retry = setInterval(() => {
      void run();
    }, 1500);
    return () => {
      active = false;
      abort.abort();
      if (retry) clearInterval(retry);
    };
  }, [task, revision, token]);
  return (
    <section aria-label="Agent event timeline">
      <h2>Agent events</h2>
      <small>
        Durable replay and live execution facts · revision {revision}
      </small>
      {error && <p role="status">{error}</p>}
      <ol>
        {events.map((e) => (
          <li key={e.cursor} data-cursor={e.cursor}>
            <strong>{e.event_type.replaceAll(".", " ")}</strong>
            <small>
              {new Date(e.timestamp * 1000).toLocaleTimeString()} · {e.runtime}{" "}
              · {e.model} · execution {e.execution_id} / {e.sequence}
            </small>
            {typeof e.payload.tool === "string" ? (
              <code>{e.payload.tool}</code>
            ) : null}
            {typeof e.payload.activity === "string" ? (
              <p>{e.payload.activity}</p>
            ) : null}
            {typeof e.payload.exit_code === "number" ? (
              <span>Exit {String(e.payload.exit_code)}</span>
            ) : null}
          </li>
        ))}
      </ol>
      {!events.length && !error && (
        <p>No execution events recorded for this revision yet.</p>
      )}
    </section>
  );
}
