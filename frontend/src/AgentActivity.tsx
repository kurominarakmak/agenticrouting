import type { AgentCall, Message, Task } from "./api";

const roleIcons: Record<string, string> = {
  worker: "⌘",
  reviewer: "⌕",
  supervisor: "◆",
  planner: "≡",
  researcher: "◎",
  subagent: "↳",
  assistant: "✦",
};

function AgentIcon({ role }: { role: string }) {
  return (
    <span className="agent-role-icon" data-role={role} aria-hidden="true">
      {roleIcons[role] ?? "●"}
    </span>
  );
}

const relativeTime = new Intl.RelativeTimeFormat(undefined, { style: "narrow" });

function CallTime({ seconds, prefix }: { seconds: number; prefix?: string }) {
  const time = new Date(seconds * 1000);
  const minutes = Math.max(0, Math.floor((Date.now() - time.getTime()) / 60_000));
  const age = minutes >= 1440
    ? relativeTime.format(-Math.floor(minutes / 1440), "day")
    : minutes >= 60
      ? relativeTime.format(-Math.floor(minutes / 60), "hour")
      : minutes > 0 ? relativeTime.format(-minutes, "minute") : "just now";
  return (
    <time dateTime={time.toISOString()} title={time.toLocaleString()}>
      {prefix}{age}
    </time>
  );
}

function latestChatReply(messages: Message[]) {
  for (const message of messages.slice().reverse()) {
    if (message.role !== "assistant" || message.task_id) continue;
    try {
      const { route, blocked } = JSON.parse(message.meta);
      if (blocked || route?.blocked_reason || route?.mode !== "chat" || typeof route.runtime !== "string") continue;
      const label = route.runtime === "deterministic" ? "Built-in answer" : "Assistant";
      return { label, time: message.created };
    } catch {
      continue;
    }
  }
}

export function AgentActivity({
  tasks,
  calls,
  messages,
  busy,
  openTask,
}: {
  tasks: Task[];
  calls: AgentCall[];
  messages: Message[];
  busy: boolean;
  openTask: (taskId: string) => void;
}) {
  const rootTasks = tasks.filter((task) => !task.parent_id);
  const current = rootTasks.find((task) => task.column === "In Progress") ?? rootTasks[0];
  const finished = current?.status === "done";
  const subagents = tasks.filter((task) => task.parent_id);
  const reply = latestChatReply(messages);
  const complete = subagents.filter((task) => task.column === "Done").length;

  return (
    <aside className="agent-activity" id="agent-activity" aria-labelledby="agent-activity-title">
      <h2 id="agent-activity-title">Agent activity</h2>
      {busy && <p role="status">Processing your message…</p>}
      {current && (
        <section>
          <h3>Task status</h3>
          <button className={finished ? "agent-activity-link agent-task-done" : "agent-activity-link"} onClick={() => openTask(current.id)}>
            <strong>{current.status.replaceAll("_", " ")}</strong>
            {finished ? (
              current.completed_at ? <CallTime seconds={current.completed_at} /> : null
            ) : (
              <>
                <span>{current.activity || current.title}</span>
                {current.started_at ? <CallTime seconds={current.started_at} prefix="Started " /> : null}
              </>
            )}
          </button>
        </section>
      )}
      {subagents.length > 0 && (
        <section>
          <h3>Subagents <small>{complete} of {subagents.length} done</small></h3>
          <ul>
            {subagents.map((task) => (
              <li key={task.id}>
                <button className="agent-activity-link agent-call" title={task.title} onClick={() => openTask(task.id)}>
                  <AgentIcon role="subagent" />
                  <strong>Subagent</strong>
                  {task.started_at ? <CallTime seconds={task.started_at} /> : <span>{task.status.replaceAll("_", " ")}</span>}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {calls.length > 0 && (
        <section>
          <h3>Recent agent calls</h3>
          <ul>
            {calls.map((call) => (
              <li key={call.id}>
                <button className="agent-activity-link agent-call" onClick={() => openTask(call.task_id)}>
                  <AgentIcon role={call.role} />
                  <strong>{call.role.replaceAll("_", " ")}</strong>
                  <CallTime seconds={call.created} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {reply && (
        <section>
          <h3>Latest chat reply</h3>
          <div className="agent-activity-link agent-call">
            <AgentIcon role="assistant" />
            <strong>{reply.label}</strong>
            <CallTime seconds={reply.time} />
          </div>
        </section>
      )}
      {!current && !subagents.length && !calls.length && !reply && !busy && (
        <p>Send a message to see agent activity.</p>
      )}
    </aside>
  );
}
