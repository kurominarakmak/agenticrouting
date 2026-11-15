import { test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";
test("legacy versus React idle samples", async ({ browser }) => {
  const token = readFileSync(
    `${homedir()}/Library/Application Support/Personal AI Work/state/token`,
    "utf8",
  ).trim();
  const results = [];
  for (const path of ["/legacy/", "/ui/"]) {
    const page = await browser.newPage();
    await page.addInitScript(
      (t) => sessionStorage.setItem("pawToken", t),
      token,
    );
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("Performance.enable");
    await page.goto("http://127.0.0.1:8788" + path);
    await page
      .getByRole("button", { name: "Notifications", exact: true })
      .waitFor();
    const before = await cdp.send("Performance.getMetrics");
    await page.waitForTimeout(5000);
    const after = await cdp.send("Performance.getMetrics");
    const metric = (data: typeof before, name: string) =>
      data.metrics.find((x) => x.name === name)?.value || 0;
    results.push({
      path,
      js_heap_bytes: metric(after, "JSHeapUsedSize"),
      idle_main_thread_ms:
        (metric(after, "TaskDuration") - metric(before, "TaskDuration")) * 1000,
      sample_seconds: 5,
    });
    await page.close();
  }
  console.log(
    JSON.stringify(
      {
        browser_idle_samples: results,
        scope:
          "One Chromium sample per frontend on the same host, not a statistical performance claim.",
      },
      null,
      2,
    ),
  );
});
