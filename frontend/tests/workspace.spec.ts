import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
const origin = new URL(process.env.SYNTROPIC_URL || "http://127.0.0.1:8788/ui/")
  .origin;
const token = readFileSync(
  process.env.SYNTROPIC_TOKEN_FILE ||
    `${homedir()}/Library/Application Support/Personal AI Work/state/token`,
  "utf8",
).trim();
test.beforeEach(async ({ page }) => {
  await page.addInitScript((t) => sessionStorage.setItem("pawToken", t), token);
  await page.goto("");
  await expect(
    page.getByRole("button", { name: "Notifications", exact: true }),
  ).toBeVisible();
});
test("real task state and inspector agree with the API", async ({
  page,
  request,
}) => {
  const r = await request.get(origin + "/api/state", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const s = await r.json();
  await page.getByRole("button", { name: "Tasks", exact: true }).click();
  for (const col of ["To Do", "In Progress", "In Review", "Blocked", "Done"])
    await expect(
      page.getByRole("heading", {
        name: `${col} ${s.tasks.filter((t: { column: string }) => t.column === col).length}`,
        exact: true,
      }),
    ).toBeVisible();
  const task = s.tasks.find((t: { status: string }) => t.status === "done");
  test.skip(!task, "No real completed task on this host");
  await page.locator(`[data-task-id="${task.id}"]`).click();
  await expect(
    page.getByRole("dialog", { name: "Task inspector" }),
  ).toContainText(task.activity);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("chat waits for the workspace before submitting", async ({ page }) => {
  let resume!: () => void;
  const ready = new Promise<void>((resolve) => { resume = resolve; });
  await page.route("**/api/state?**", async (route) => {
    await ready;
    await route.continue();
  });
  try {
    await page.reload();
    await page.getByLabel("Message", { exact: true }).fill("Implement greeting.py.");
    await expect(page.getByRole("button", { name: "Send message" })).toBeDisabled();
  } finally {
    resume();
  }
  await expect(page.getByRole("button", { name: "Send message" })).toBeEnabled();
});
test("local stream persists without creating a job", async ({
  page,
  request,
}) => {
  const state = () =>
    request
      .get(origin + "/api/state", {
        headers: { Authorization: `Bearer ${token}` },
      })
      .then((r) => r.json());
  const before = await state();
  await page
    .getByLabel("Message", { exact: true })
    .fill("How many legs does a dog have?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByText("A dog normally has four legs.", { exact: true }),
  ).toBeVisible();
  expect((await state()).task_total).toBe(before.task_total);
});

test("chat uses the first allowlisted repository when demo is unavailable", async ({ page, request }) => {
  const response = await request.get(origin + "/api/state", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const state = await response.json();
  const expected = state.resources.repositories[0];
  test.skip(!expected || state.resources.repositories.includes("demo"), "This state still allowlists demo");
  await expect(page.getByLabel("Repository", { exact: true })).toHaveValue(expected);
  let submitted: Record<string, unknown> | undefined;
  await page.route("**/api/chat/stream", async (route) => {
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      headers: { "content-type": "application/x-ndjson" },
      body: JSON.stringify({ type: "result", data: { conversation: "playwright-fixture" } }) + "\n",
    });
  });
  await page.getByLabel("Message", { exact: true }).fill("fixture-only question");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect.poll(() => submitted?.repo).toBe(expected);
});
test("chat shows the recorded agents and times for its own task", async ({ page, request }) => {
  const headers = { Authorization: `Bearer ${token}` };
  const state = await request.get(origin + "/api/state", { headers }).then((r) => r.json());
  const task = state.tasks.find((item: { status: string }) => item.status === "done");
  test.skip(!task, "A completed fixture task is required");
  const { agent_calls } = await request.get(
    origin + "/api/state?conversation=" + encodeURIComponent(task.conversation), { headers },
  ).then((r) => r.json());
  test.skip(!agent_calls?.length, "A recorded agent call is required");
  const call = agent_calls[0];
  await page.clock.setFixedTime(new Date((call.created + 4 * 3600 + 60) * 1000));
  await page.addInitScript((id) => localStorage.setItem("pawConversation", id), task.conversation);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();

  const toggle = page.getByRole("button", { name: "Agents", exact: true });
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  const activity = page.getByRole("complementary", { name: "Agent activity" });
  await expect(activity.getByRole("heading", { name: "Recent agent calls" })).toBeVisible();
  const completed = activity.getByRole("button", { name: /^done 4h ago$/i });
  await expect(completed).toBeVisible();
  await expect(completed.locator("time")).toHaveAttribute("datetime", new Date(task.completed_at * 1000).toISOString());
  const row = activity.getByRole("button", { name: new RegExp(call.role, "i") }).first();
  await expect(row).not.toContainText(call.model);
  await expect(row.locator("time")).toHaveText("4h ago");
  await expect(row.locator("time")).toHaveAttribute("datetime", new Date(call.created * 1000).toISOString());
  await row.click({ timeout: 5000 });
  await expect(page.getByRole("dialog", { name: "Task inspector" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);

  await page.getByRole("button", { name: "Toggle sidebar" }).click();
  await page.getByRole("button", { name: "＋ New chat", exact: true }).click();
  await expect(activity.getByRole("heading", { name: "Recent agent calls" })).toHaveCount(0);
  await page.getByLabel("Message", { exact: true }).fill("How many legs does a dog have?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(activity.getByText("Built-in answer", { exact: true })).toBeVisible();
});
test("mobile navigation is keyboard accessible and fits", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Toggle sidebar" }).click();
  await page.getByRole("button", { name: "Knowledge", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Knowledge & MCP", exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    390,
  );
});

test("durable timeline replays in order after reconnect without duplicates", async ({
  page,
  request,
}) => {
  const snapshot = await request
    .get(origin + "/api/state", {
      headers: { Authorization: `Bearer ${token}` },
    })
    .then((r) => r.json());
  const task = snapshot.tasks.find(
    (t: { status: string; parent_id: string | null }) =>
      t.status === "done" && !t.parent_id,
  );
  test.skip(!task, "No real completed parent");
  async function open() {
    await page.getByRole("button", { name: "Tasks", exact: true }).click();
    await page.locator(`[data-task-id="${task.id}"]`).click();
    await expect(
      page
        .getByRole("region", { name: "Agent event timeline" })
        .locator("li")
        .first(),
    ).toBeVisible();
  }
  await open();
  const first = await page
    .getByRole("region", { name: "Agent event timeline" })
    .locator("li")
    .first()
    .getAttribute("data-cursor");
  await page.context().setOffline(true);
  await page.context().setOffline(false);
  await page.reload();
  await open();
  await expect(page.locator(`[data-cursor="${first}"]`)).toBeVisible();
  const cursors = await page
    .getByRole("region", { name: "Agent event timeline" })
    .locator("li")
    .evaluateAll((nodes) =>
      nodes.map((n) => Number(n.getAttribute("data-cursor"))),
    );
  expect(cursors).toEqual([...new Set(cursors)].sort((a, b) => a - b));
});

test("rich module failure keeps the workspace and persisted reply usable", async ({
  page,
}) => {
  await page.route("**/prose-*.js", (route) => route.abort());
  await page.reload();
  await page.getByRole("button", { name: "＋ New chat", exact: true }).click();
  await page
    .getByLabel("Message", { exact: true })
    .fill("How many legs does a dog have?");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByText("A dog normally has four legs.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reload formatting" }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Tasks", exact: true }),
  ).toBeVisible();
});

test("provider settings persist and bind a manual planner model without inference", async ({ page, request }) => {
  const initial = await request.get(origin + "/api/state", { headers: { Authorization: `Bearer ${token}` } });
  const original = (await initial.json()).settings.orchestration;
  const restorable = JSON.parse(JSON.stringify(original));
  for (const provider of Object.values(restorable.providers) as Record<string, unknown>[]) delete provider.credential_configured;
  try {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("New provider ID").fill("browser-fixture");
  await page.getByRole("button", { name: "Add provider", exact: true }).click();
  const provider = page.locator(".provider-editor").filter({ hasText: "browser-fixture" });
  await provider.getByLabel("Enabled").check();
  await provider.getByLabel("browser-fixture model IDs").fill("fixture-model-v1");

  await page.getByLabel("planner selection").selectOption("manual");
  await page.getByLabel("planner Enabled").check();
  await page.getByLabel("planner provider").selectOption("browser-fixture");
  await page.getByLabel("planner model").fill("fixture-model-v1");
  await page.getByRole("button", { name: "Save provider and orchestration settings" }).click();
  await expect.poll(async () => {
    const response = await request.get(origin + "/api/state", { headers: { Authorization: `Bearer ${token}` } });
    const state = await response.json();
    return state.settings.orchestration;
  }, { timeout: 10000 }).toMatchObject({
    providers: { "browser-fixture": { models: ["fixture-model-v1"] } },
    roles: { planner: { mode: "manual", enabled: true, backend: "api", provider: "browser-fixture", model: "fixture-model-v1" } },
  });
  const response = await request.get(origin + "/api/state", { headers: { Authorization: `Bearer ${token}` } });
  const persisted = await response.json();
  const stored = persisted.settings.orchestration;
  expect(stored.providers["browser-fixture"].models).toEqual(["fixture-model-v1"]);
  expect(stored.roles.planner).toMatchObject({ mode: "manual", enabled: true, backend: "api", provider: "browser-fixture", model: "fixture-model-v1" });
  expect(JSON.stringify(stored.providers["browser-fixture"])).not.toContain("secret_ref");
  await page.reload();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.getByLabel("planner selection")).toHaveValue("manual");
  await expect(page.getByLabel("planner provider")).toHaveValue("browser-fixture");
  await expect(page.getByLabel("planner model")).toHaveValue("fixture-model-v1");
  } finally {
    const restored = await request.post(origin + "/api/settings", {
      headers: { Authorization: `Bearer ${token}` },
      data: { orchestration: restorable },
    });
    expect(restored.ok()).toBeTruthy();
  }
});

test("prepared PR status and confirmed link render from the task delivery snapshot", async ({ page, request }) => {
  const response = await request.get(origin + "/api/state", { headers: { Authorization: `Bearer ${token}` } });
  const state = await response.json();
  const task = state.tasks.find((candidate: { delivery?: { status?: string; pr_url?: string | null } }) => candidate.delivery);
  test.skip(!task, "No prepared delivery fixture is available");
  await page.getByRole("button", { name: "Tasks", exact: true }).click();
  await page.locator(`[data-task-id="${task.id}"]`).click();
  const delivery = page.getByRole("region", { name: "Prepared pull request" });
  await expect(delivery).toContainText(`Status: ${task.delivery.status}`);
  if (task.delivery.pr_url) {
    await expect(delivery.getByRole("link", { name: "Open confirmed pull request" })).toHaveAttribute("href", task.delivery.pr_url);
  }
});
