"use client";

// Two small comparisons for one saved run and split. The table next to them is the
// accessible, exact version; these charts are a visual summary of the same values.
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatRecall, type MethodSummary } from "@/lib/dashboard";

const AXIS = { fill: "var(--color-muted)", fontSize: 12 };
const GRID = "var(--color-line)";
const TOOLTIP = {
  contentStyle: { background: "var(--color-card)", border: "1px solid var(--color-line-strong)", borderRadius: 9, color: "var(--color-ink)" },
  labelStyle: { color: "var(--color-ink)" },
  cursor: { fill: "var(--color-strip)" },
};

function short(label: string): string {
  return label.replace(/ \(.*\)$/, "");
}

export function RecallChart({ methods }: { methods: MethodSummary[] }) {
  const data = methods.map((m) => ({ name: short(m.label), recall: m.recall.value, n: m.recall.n }));
  return (
    <figure className="m-0">
      <figcaption className="mb-3 text-sm text-muted">Recall@5, answerable questions (article-level, 0–1)</figcaption>
      <div className="h-56" role="img" aria-label="Bar chart of Recall@5 per method; exact values are in the comparison table.">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 22, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="name" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} interval={0} />
            <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tick={AXIS} axisLine={false} tickLine={false} />
            <Tooltip {...TOOLTIP} formatter={(value) => [formatRecall(typeof value === "number" ? value : null), "Recall@5"]} />
            <Bar dataKey="recall" fill="var(--color-accent)" radius={[4, 4, 0, 0]} maxBarSize={56} isAnimationActive={false}>
              <LabelList dataKey="recall" position="top" fill="var(--color-ink)" fontSize={12} formatter={(v) => (typeof v === "number" ? formatRecall(v) : "")} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

export function LatencyChart({ methods }: { methods: MethodSummary[] }) {
  const data = methods.map((m) => ({ name: short(m.label), median: m.latency.median, p95: m.latency.p95 }));
  return (
    <figure className="m-0">
      <figcaption className="mb-3 text-sm text-muted">Retrieval latency, milliseconds (query embedding excluded)</figcaption>
      <div className="h-56" role="img" aria-label="Bar chart of median and p95 retrieval latency per method; exact values are in the comparison table.">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 22, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="name" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} interval={0} />
            <YAxis tick={AXIS} axisLine={false} tickLine={false} unit=" ms" width={64} />
            <Tooltip {...TOOLTIP} formatter={(value, name) => [typeof value === "number" ? `${value} ms` : "Not measured", name]} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={(value) => <span style={{ color: "var(--color-muted)" }}>{value}</span>} />
            <Bar name="Median" dataKey="median" fill="var(--color-accent)" radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false}>
              <LabelList dataKey="median" position="top" fill="var(--color-ink)" fontSize={11} formatter={(v) => (typeof v === "number" ? v.toFixed(1) : "")} />
            </Bar>
            <Bar name="p95" dataKey="p95" fill="var(--color-accent-tint)" stroke="var(--color-accent)" radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false}>
              <LabelList dataKey="p95" position="top" fill="var(--color-ink)" fontSize={11} formatter={(v) => (typeof v === "number" ? v.toFixed(1) : "")} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
