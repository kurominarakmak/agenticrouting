import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
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
  const r = await request.get("http://127.0.0.1:8788/api/state", {
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
  await page
    .getByRole("button")
    .filter({
      has: page.getByRole("heading", { name: task.title, exact: true }),
    })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Task inspector" }),
  ).toContainText(task.activity);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("local stream persists without creating a job", async ({
  page,
  request,
}) => {
  const state = () =>
    request
      .get("http://127.0.0.1:8788/api/state", {
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
