import { useState, useEffect, useRef, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { Button } from "./vendor/Button";
import { api, stream, type Task, type Snapshot } from "./api";
import { Prose, Json, Structured } from "./renderers";

import "./style.css";
const columns = ["To Do", "In Progress", "In Review", "Blocked", "Done"];
const pages = [
  "Chat",
  "Tasks",
  "Knowledge",
  "Models / Harnesses",
  "Settings",
] as const;
type Page = (typeof pages)[number];
function Badge({ children }: { children: ReactNode }) {
  return <span className="badge">{children}</span>;
}
function Modal({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      aria-label={title}
    >
      <div className="dialog-header">
        <h2>{title}</h2>
        <Button onClick={close} aria-label="Close dialog">
          ✕
        </Button>
      </div>
      {children}
    </dialog>
  );
}
function App() {
  const [token, setToken] = useState(sessionStorage.getItem("pawToken") || ""),
    [entry, setEntry] = useState(""),
    [s, setS] = useState<Snapshot | null>(null),
    [conversation, setConversation] = useState(
      localStorage.getItem("pawConversation") || "",
    ),
    [page, setPage] = useState<Page>("Chat"),
    [selected, setSelected] = useState<string | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [live, setLive] = useState(""),
    [prompt, setPrompt] = useState(""),
    [route, setRoute] = useState("auto"),
    [repo, setRepo] = useState("demo"),
    [drawer, setDrawer] = useState(false),
    [notifications, setNotifications] = useState(false),
    [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [knowledge, setKnowledge] = useState<unknown>(null),
    [artifact, setArtifact] = useState<{ path: string; text: string } | null>(
      null,
    ),
    [history, setHistory] = useState<Task[]>([]),
    [olderConversations, setOlderConversations] = useState<
      Snapshot["conversations"]
    >([]);
  useEffect(() => setArtifact(null), [selected]);
  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawer(false);
    };
    window.addEventListener("keydown", handle);
    return () => window.removeEventListener("keydown", handle);
  }, []);
  const lastNotification = useRef(0);
  const latest = useRef(0);
  async function refresh() {
    if (!token) return;
    const n = ++latest.current;
    try {
      const data = await api<Snapshot>(
        token,
        "/api/state?conversation=" +
          encodeURIComponent(conversation) +
          (selected ? "&task=" + encodeURIComponent(selected) : ""),
      );
      if (n === latest.current) {
        if (
          data.settings.notifications &&
          lastNotification.current &&
          "Notification" in window &&
          Notification.permission === "granted"
        )
          for (const n of data.notifications.filter(
            (n) => n.id > lastNotification.current,
          ))
            new Notification("Syntropic", { body: n.text, tag: String(n.id) });
        lastNotification.current = Math.max(
          lastNotification.current,
          ...data.notifications.map((n) => n.id),
        );
        setS(data);
        setError("");
      }
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2500);
    return () => {
      clearInterval(id);
      latest.current++;
    };
  }, [token, conversation, selected]);
  function choose(id: string) {
    setConversation(id);
    localStorage.setItem("pawConversation", id);
    setPage("Chat");
    setDrawer(false);
  }
  async function action(path: string, data: unknown) {
    try {
      const out = await api<unknown>(token, path, data);
      await refresh();
      return out;
    } catch (e) {
      setError(String(e));
    }
  }
  const tasks = [
      ...(s?.tasks || []),
      ...history.filter((t) => !s?.tasks.some((x) => x.id === t.id)),
    ],
    active = tasks.filter(
      (t) => !["done", "archived", "cancelled"].includes(t.status),
    ),
    task = tasks.find((t) => t.id === selected);
  function card(t: Task) {
    return (
      <Button
        key={t.id}
        className="task-card"
        onClick={() => setSelected(t.id)}
      >
        <Badge>{t.status.replaceAll("_", " ")}</Badge>
        <h3>{t.title}</h3>
        <p>{t.activity}</p>
        <small>
          {t.route.runtime} · revision {t.revision}
        </small>
      </Button>
    );
  }
  async function send() {
    if (busy || !prompt.trim()) return;
    setBusy(true);
    setLive("Selecting a compatible runtime…");
    setError("");
    let received = false,
      output = "";
    try {
      await stream(
        token,
        {
          text: prompt,
          conversation: conversation || null,
          repo,
          override: route,
        },
        (e) => {
          if (e.type === "delta") {
            output += e.text;
            setLive(output);
          }
          if (e.type === "error") throw Error(e.error);
          if (e.type === "result") {
            received = true;
            choose(e.data.conversation);
            setPrompt("");
          }
        },
      );
      if (!received)
        throw Error(
          "Connection closed before final result. Check history before retrying.",
        );
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
      if (received) setLive("");
      await refresh();
    }
  }
  return (
    <>
      <div className={drawer ? "shell sidebar-open" : "shell"}>
        <aside aria-label="Workspace sidebar">
          <div className="brand">
            ✳ <strong>Syntropic</strong>
            <small>Personal AI Work</small>
          </div>
          <Button className="new-chat" onClick={() => choose("")}>
            ＋ New chat
          </Button>
          <nav aria-label="Workspace">
            {pages.map((p) => (
              <Button
                key={p}
                className={page === p ? "selected" : ""}
                onClick={() => {
                  setPage(p);
                  setDrawer(false);
                }}
              >
                {p}
              </Button>
            ))}
          </nav>
          <h2>
            Active tasks <Badge>{active.length}</Badge>
          </h2>
          {active.slice(0, 8).map((t) => (
            <Button
              key={t.id}
              className="sidebar-item"
              onClick={() => {
                setSelected(t.id);
                setDrawer(false);
              }}
            >
              {t.title}
              <small>{t.activity || t.status}</small>
            </Button>
          ))}
          <h2>Recent conversations</h2>
          {[
            ...(s?.conversations || []),
            ...olderConversations.filter(
              (c) => !s?.conversations.some((x) => x.id === c.id),
            ),
          ].map((c) => (
            <Button
              className="sidebar-item"
              key={c.id}
              onClick={() => choose(c.id)}
            >
              {c.title}
            </Button>
          ))}
          {s &&
            s.conversation_total >
              s.conversations.length + olderConversations.length && (
              <Button
                onClick={async () => {
                  try {
                    setOlderConversations([
                      ...olderConversations,
                      ...(await api<Snapshot["conversations"]>(
                        token,
                        "/api/conversations?offset=" +
                          (s.conversations.length + olderConversations.length),
                      )),
                    ]);
                  } catch (e) {
                    setError(String(e));
                  }
                }}
              >
                Older conversations
              </Button>
            )}
        </aside>
        <div className="workspace">
          <header>
            <Button
              aria-label="Toggle sidebar"
              aria-expanded={drawer}
              onClick={() => setDrawer(!drawer)}
            >
              ☰
            </Button>
            <strong>{page}</strong>
            <span className="health">
              {s?.worker.online ? "● Home worker online" : "○ Worker offline"}
            </span>
            <Button
              onClick={() => setNotifications(true)}
              aria-label="Notifications"
            >
              ♧ {s?.notifications.length || 0}
            </Button>
          </header>
          {error && (
            <p role="alert" className="notice">
              {error}
            </p>
          )}
          <main id="main">
            {page === "Chat" && (
              <div className="chat-stream">
                {!s?.messages.length && !busy && (
                  <div className="empty">
                    <span>✳</span>
                    <h1>What’s on your mind?</h1>
                    <p>Ask, explore, or describe the work you want done.</p>
                  </div>
                )}
                {s?.messages.map((m) => {
                  let meta: Record<string, unknown> = {};
                  try {
                    meta = JSON.parse(m.meta || "{}");
                  } catch {}
                  const linked = tasks.find((t) => t.id === m.task_id);
                  return (
                    <article key={m.id} className={"chat-message " + m.role}>
                      <span>{m.role === "user" ? "You" : "✳"}</span>
                      <div className="message-body">
                        {meta.verification &&
                        typeof meta.verification === "object" &&
                        "exit_code" in meta.verification &&
                        meta.verification.exit_code === 0 ? (
                          <>
                            <p>✓ Independent acceptance passed</p>
                            <Json
                              value={meta.verification}
                              label="Verification receipt"
                            />
                            <details>
                              <summary>Agent observations</summary>
                              <Prose
                                text={String(meta.agent_summary || m.text)}
                              />
                            </details>
                          </>
                        ) : (
                          <Prose text={m.text} />
                        )}{" "}
                        {meta.sources ? (
                          <Json
                            value={meta.sources}
                            label="Sources and provenance"
                          />
                        ) : null}
                        {meta.tool_result ? (
                          <Structured value={meta.tool_result} />
                        ) : null}
                        {linked && card(linked)}
                      </div>
                    </article>
                  );
                })}
                {busy && (
                  <article aria-live="polite">
                    <p>{prompt}</p>
                    <Prose text={live} />
                  </article>
                )}
              </div>
            )}
            {page === "Tasks" && (
              <>
                <h1>Tasks</h1>
                <p className="subtle">
                  Created from chat. Status comes from the independent worker.
                </p>
                <div className="toolbar">
                  <input
                    aria-label="Search tasks"
                    placeholder="Search tasks…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <select
                    aria-label="Filter status"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    {[
                      "all",
                      "active",
                      "failed",
                      "cancelled",
                      "paused",
                      "awaiting_approval",
                      "done",
                    ].map((f) => (
                      <option key={f}>{f}</option>
                    ))}
                  </select>
                </div>
                <div className="kanban">
                  {columns.map((c) => (
                    <section className="lane" key={c}>
                      <h2>
                        {c}{" "}
                        <Badge>
                          {tasks.filter((t) => t.column === c).length}
                        </Badge>
                      </h2>
                      {tasks
                        .filter(
                          (t) =>
                            t.column === c &&
                            (filter === "all" ||
                              (filter === "active"
                                ? active.includes(t)
                                : t.status === filter)) &&
                            (t.title + " " + t.id)
                              .toLowerCase()
                              .includes(query.toLowerCase()),
                        )
                        .map(card)}
                    </section>
                  ))}
                </div>
                {s && tasks.length < s.task_total && (
                  <Button
                    onClick={async () => {
                      try {
                        const old = await api<Snapshot>(
                          token,
                          "/api/state?offset=" + tasks.length,
                        );
                        setHistory([...history, ...old.tasks]);
                      } catch (e) {
                        setError(String(e));
                      }
                    }}
                  >
                    Load older tasks
                  </Button>
                )}
              </>
            )}
            {page === "Models / Harnesses" && (
              <>
                <h1>Models & Harnesses</h1>
                <p>
                  Observed capabilities · subscription quota remains unknown.
                </p>
                <Button
                  onClick={async () => {
                    await api(token, "/api/models?refresh=1");
                    await refresh();
                  }}
                >
                  Refresh inventory
                </Button>
                {s?.registry.runtimes.map((r) => (
                  <article className="card" key={r.id}>
                    <h2>{r.name}</h2>
                    <Badge>
                      {r.available ? "Available" : "Unavailable / unconfigured"}
                    </Badge>
                    <p>{r.authentication}</p>
                    <p>{r.capabilities.join(" · ")}</p>
                    <Json value={r} />
                  </article>
                ))}
                <Json value={s?.routing_history} label="Routing decisions" />
              </>
            )}
            {page === "Knowledge" && (
              <>
                <h1>Knowledge & MCP</h1>
                <form
                  className="toolbar"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      setKnowledge(
                        await api(
                          token,
                          "/api/knowledge?q=" + encodeURIComponent(query),
                        ),
                      );
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  <input
                    aria-label="Search knowledge"
                    placeholder="Search scoped knowledge…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <Button type="submit">Search</Button>
                </form>
                {knowledge ? (
                  <Json
                    value={knowledge}
                    label="Search results and provenance"
                  />
                ) : null}
                {s?.knowledge.roots.map((r) => (
                  <article className="card" key={r.id}>
                    <h2>{r.id}</h2>
                    <p>{r.path}</p>
                    <Badge>
                      {r.share_frontier
                        ? "Frontier sharing allowed"
                        : "Local only"}
                    </Badge>
                    <Button
                      onClick={() =>
                        action("/api/knowledge/index", { root: r.id })
                      }
                    >
                      Sync
                    </Button>
                  </article>
                ))}
                <Memory save={(data) => action("/api/memory", data)} />
                {s?.knowledge.memories.map((m, i) => (
                  <article className="card" key={i}>
                    <Badge>{m.kind}</Badge>
                    <p>{m.text}</p>
                    <small>
                      {m.frontier ? "Frontier sharing allowed" : "Local only"}
                    </small>
                  </article>
                ))}
                <h2>Authorized MCP servers</h2>
                {!s?.tools.length && (
                  <p>
                    No servers configured. Account access is not inherited from
                    this chat.
                  </p>
                )}
                {s?.tools.map((t) => (
                  <article className="card" key={t.name}>
                    <h3>{t.name}</h3>
                    <Badge>
                      {t.enabled
                        ? "Configured, connection unverified"
                        : "Disabled"}
                    </Badge>
                    <Json value={t} />
                    <Button
                      onClick={async () =>
                        setKnowledge(
                          await action("/api/tools/discover", {
                            server: t.name,
                          }),
                        )
                      }
                    >
                      Discover tools
                    </Button>
                  </article>
                ))}
              </>
            )}
            {page === "Settings" && (
              <>
                <h1>Settings</h1>
                <Structured
                  value={{
                    type: "chart",
                    values: columns.map((label) => ({
                      label,
                      value: tasks.filter((t) => t.column === label).length,
                    })),
                  }}
                />
                <label className="card">
                  Default routing
                  <select
                    value={s?.settings.routing || "auto"}
                    onChange={(e) =>
                      action("/api/settings", { routing: e.target.value })
                    }
                  >
                    {[
                      "auto",
                      "local-only",
                      "codex-chatgpt",
                      "claude-subscription",
                      "glm-coding-plan",
                    ].map((x) => (
                      <option key={x}>{x}</option>
                    ))}
                  </select>
                </label>
                <label className="card">
                  <input
                    type="checkbox"
                    checked={s?.settings.review_before_done || false}
                    onChange={(e) =>
                      action("/api/settings", {
                        review_before_done: e.target.checked,
                      })
                    }
                  />{" "}
                  Review verified changes before completion
                </label>
                <Button
                  onClick={async () => {
                    if ("Notification" in window)
                      await Notification.requestPermission();
                  }}
                >
                  Enable browser alerts
                </Button>
                <p>
                  Private remote setup: <code>python3 ops.py remote</code>.
                  Requires Tailscale Serve and token authentication.
                </p>
                <Button
                  onClick={() => {
                    sessionStorage.removeItem("pawToken");
                    setToken("");
                    setS(null);
                  }}
                >
                  Sign out
                </Button>
                <Json value={s?.settings} label="Current settings" />
              </>
            )}
          </main>
          {page === "Chat" && (
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                void send();
              }}
            >
              <label className="sr-only" htmlFor="prompt">
                Message
              </label>
              <textarea
                id="prompt"
                placeholder="Ask anything or run an autonomous task…"
                value={prompt}
                maxLength={12000}
                onChange={(e) => setPrompt(e.target.value)}
                required
              />
              <div className="composer-toolbar">
                <select
                  aria-label="Routing mode"
                  value={route}
                  onChange={(e) => setRoute(e.target.value)}
                >
                  {[
                    "auto",
                    "local-only",
                    "codex-chatgpt",
                    "claude-subscription",
                    "glm-coding-plan",
                    ...(s?.registry.runtimes
                      .filter((r) => ["ollama", "lmstudio"].includes(r.harness))
                      .map((r) => r.id) || []),
                  ].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
                <select
                  aria-label="Repository"
                  value={repo}
                  onChange={(e) => setRepo(e.target.value)}
                >
                  {s?.resources.repositories.map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
                <Button
                  type="submit"
                  className="send"
                  disabled={busy}
                  aria-label="Send message"
                >
                  ↑
                </Button>
              </div>
              <small>
                Work continues on your home computer after this browser closes.
              </small>
            </form>
          )}
        </div>
      </div>
      {!token && (
        <Modal title="Welcome home" close={() => {}}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api(entry, "/api/state");
                sessionStorage.setItem("pawToken", entry);
                setToken(entry);
                setEntry("");
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            <label>
              Service token
              <input
                type="password"
                value={entry}
                onChange={(e) => setEntry(e.target.value)}
              />
            </label>
            <label>
              Choose local token file
              <input
                type="file"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (f && f.size < 1000) setEntry((await f.text()).trim());
                }}
              />
            </label>
            <Button type="submit">Connect workspace</Button>
          </form>
        </Modal>
      )}
      {task && (
        <Modal
          title="Task inspector"
          close={() => {
            setSelected(null);
            setArtifact(null);
          }}
        >
          <Badge>{task.status}</Badge>
          <h1>{task.title}</h1>
          <p>{task.activity}</p>
          <p>
            {task.route.runtime} · revision {task.revision} · attempts{" "}
            {task.attempts}
          </p>
          {task.error && <p role="alert">{task.error}</p>}
          <div className="toolbar">
            <Button
              onClick={() => {
                choose(task.conversation);
                setSelected(null);
              }}
            >
              Open conversation
            </Button>
            {[
              ...(task.approval === "pending" ? ["approve"] : []),
              ...(task.status === "review" ? ["accept_review"] : []),
              ...(["blocked", "failed", "cancelled", "triage"].includes(
                task.status,
              )
                ? ["retry"]
                : []),
              ...(task.status === "paused" ? ["resume"] : []),
              ...([
                "running",
                "planning",
                "verifying",
                "ready",
                "waiting_dependency",
              ].includes(task.status)
                ? ["pause"]
                : []),
              ...(!["done", "archived", "cancelled"].includes(task.status)
                ? ["cancel"]
                : []),
            ].map((a) => (
              <Button
                key={a}
                onClick={() =>
                  action("/api/task/action", {
                    task_id: task.id,
                    conversation: task.conversation,
                    action: a,
                  })
                }
              >
                {a.replaceAll("_", " ")}
              </Button>
            ))}
          </div>
          <h2>Dependencies & subtasks</h2>
          {tasks
            .filter(
              (t) =>
                t.parent_id === task.id || task.dependencies.includes(t.id),
            )
            .map(card)}
          <Json
            value={{ route: task.route, plan: task.plan }}
            label="Routing and plan"
          />
          <h2>Artifacts, logs & diffs</h2>
          {task.artifacts.map((path) => (
            <Button
              key={path}
              onClick={async () => {
                try {
                  setArtifact({
                    path,
                    text: await api<string>(
                      token,
                      "/api/artifact?path=" + encodeURIComponent(path),
                    ),
                  });
                } catch (e) {
                  setError(String(e));
                }
              }}
            >
              {path.split("/").at(-1)}
            </Button>
          ))}
          {artifact && (
            <Structured
              value={{
                type: artifact.path.endsWith(".patch") ? "diff" : "terminal",
                text: artifact.text,
              }}
            />
          )}
          <Json value={task.runs} label="Execution and verification receipts" />
          <h2>Revision activity</h2>
          {task.comments
            .slice(-30)
            .reverse()
            .map((c, i) => (
              <article className="card" key={i}>
                <small>
                  {new Date(c.created_at * 1000).toLocaleString()} · {c.author}
                </small>
                <p>{c.body}</p>
              </article>
            ))}
        </Modal>
      )}
      {notifications && (
        <Modal title="Notifications" close={() => setNotifications(false)}>
          {s?.notifications.map((n) => (
            <article className="card" key={n.id}>
              <Badge>{n.kind}</Badge>
              <p>{n.text}</p>
              {n.task_id && (
                <Button
                  onClick={() => {
                    setSelected(n.task_id!);
                    setNotifications(false);
                  }}
                >
                  View task
                </Button>
              )}
            </article>
          ))}
          <Button onClick={() => action("/api/notifications/seen", {})}>
            Mark as read
          </Button>
        </Modal>
      )}
    </>
  );
}
function Memory({ save }: { save: (data: unknown) => Promise<unknown> }) {
  const [text, setText] = useState(""),
    [kind, setKind] = useState("preference"),
    [frontier, setFrontier] = useState(false);
  return (
    <form
      className="card"
      onSubmit={async (e) => {
        e.preventDefault();
        await save({ kind, text, share_frontier: frontier });
        setText("");
      }}
    >
      <h2>Persistent memory</h2>
      <select
        aria-label="Memory type"
        value={kind}
        onChange={(e) => setKind(e.target.value)}
      >
        {["preference", "evidence", "skill"].map((k) => (
          <option key={k}>{k}</option>
        ))}
      </select>
      <textarea
        aria-label="Memory content"
        value={text}
        onChange={(e) => setText(e.target.value)}
        required
        maxLength={4000}
      />
      <label>
        <input
          type="checkbox"
          checked={frontier}
          onChange={(e) => setFrontier(e.target.checked)}
        />{" "}
        Allow frontier sharing
      </label>
      <Button type="submit">Save memory</Button>
    </form>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
