import { test } from "vitest";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { Prose } from "../src/prose";
import { Button } from "../src/vendor/Button";
test("DSH button retains native accessible properties", () => {
  const html = renderToStaticMarkup(
    <Button aria-label="Approve task" disabled>
      Approve
    </Button>,
  );
  assert.match(html, /aria-label="Approve task"/);
  assert.match(html, /disabled/);
});
test("untrusted markdown cannot emit HTML, script links or remote images", () => {
  const html = renderToStaticMarkup(
    <Prose
      text={
        "<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[unsafe](javascript:alert(1))\n\n![secret](https://tracker.invalid/pixel)"
      }
    />,
  );
  assert.doesNotMatch(html, /<script|<img|onerror|href="javascript:/);
});
test("tables, math and code render as controlled markup", () => {
  const html = renderToStaticMarkup(
    <Prose
      text={
        "| One | Two |\n|---|---|\n| 1 | 2 |\n\n$x^2$\n\n```python\ndef hello(): return 1\n```"
      }
    />,
  );
  assert.match(html, /<table>/);
  assert.match(html, /katex/);
  assert.match(html, /hljs/);
});

test("a numeric answer is not swallowed as an empty Markdown list", () => {
  assert.match(renderToStaticMarkup(<Prose text="5." />), />5\.</);
});
