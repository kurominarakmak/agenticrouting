import { lazy, Suspense } from "react";
const RichProse = lazy(() =>
  import("./prose").then((m) => ({ default: m.Prose })),
);
export function Prose({ text }: { text: string }) {
  return (
    <Suspense fallback={<pre>{text}</pre>}>
      <RichProse text={text} />
    </Suspense>
  );
}
export function Json({
  value,
  label = "Details",
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <details>
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
export type Block =
  | { type: "markdown"; text: string }
  | { type: "table"; headers: string[]; rows: string[][] }
  | { type: "terminal" | "diff"; text: string }
  | { type: "chart"; values: { label: string; value: number }[] };
const registry = {
  markdown: (b: Extract<Block, { type: "markdown" }>) => (
    <Prose text={b.text} />
  ),
  table: (b: Extract<Block, { type: "table" }>) => (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {b.headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {b.rows.slice(0, 100).map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ),
  terminal: (b: { text: string }) => <pre>{b.text}</pre>,
  diff: (b: { text: string }) => (
    <pre className="diff">
      {b.text.split("\n").map((l, i) => (
        <span
          key={i}
          className={l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : ""}
        >
          {l}
          {"\n"}
        </span>
      ))}
    </pre>
  ),
  chart: (b: Extract<Block, { type: "chart" }>) => (
    <div aria-label="Observed counts">
      {b.values.map((v) => (
        <div key={v.label}>
          {v.label}: {v.value}
          <meter
            min={0}
            max={Math.max(1, ...b.values.map((x) => x.value))}
            value={v.value}
          />
        </div>
      ))}
    </div>
  ),
};
export function Structured({ value }: { value: unknown }) {
  if (!value || typeof value !== "object") return null;
  const b = value as Record<string, unknown>;
  if (
    (b.type === "markdown" || b.type === "terminal" || b.type === "diff") &&
    typeof b.text === "string"
  )
    return registry[b.type]({ text: b.text, type: b.type } as never);
  if (
    b.type === "table" &&
    Array.isArray(b.headers) &&
    b.headers.every((x) => typeof x === "string") &&
    Array.isArray(b.rows) &&
    b.rows.every(
      (r) => Array.isArray(r) && r.every((c) => typeof c === "string"),
    )
  )
    return registry.table(b as unknown as Extract<Block, { type: "table" }>);
  if (
    b.type === "chart" &&
    Array.isArray(b.values) &&
    b.values.length <= 50 &&
    b.values.every(
      (v) =>
        v &&
        typeof v === "object" &&
        typeof v.label === "string" &&
        typeof v.value === "number" &&
        Number.isFinite(v.value) &&
        v.value >= 0,
    )
  )
    return registry.chart(b as unknown as Extract<Block, { type: "chart" }>);
  return <Json value={value} label="Structured reference data" />;
}
