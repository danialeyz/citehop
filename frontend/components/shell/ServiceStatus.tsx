"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";

type State = { kind: "checking" } | { kind: "down" } | { kind: "up"; services: Record<string, string> };

const LABELS: Record<string, string> = { mariadb: "MariaDB", neo4j: "Neo4j" };

/** Real per-service readiness from GET /api/v1/health; no uptime figures. */
export function ServiceStatus() {
  const [state, setState] = useState<State>({ kind: "checking" });

  useEffect(() => {
    let live = true;
    api
      .GET("/api/v1/health")
      .then(({ data }) => live && setState(data ? { kind: "up", services: data.services } : { kind: "down" }))
      .catch(() => live && setState({ kind: "down" }));
    return () => {
      live = false;
    };
  }, []);

  if (state.kind === "checking") return <Pill tone="neutral">Checking services…</Pill>;
  if (state.kind === "down") return <Pill tone="bad">API unreachable</Pill>;
  return (
    <ul className="flex flex-wrap gap-2" aria-label="Service status">
      {Object.entries(state.services).map(([name, status]) => (
        <li key={name}>
          <Pill tone={status === "ready" ? "good" : "bad"}>
            {LABELS[name] ?? name}: {status}
          </Pill>
        </li>
      ))}
    </ul>
  );
}

function Pill({ tone, children }: { tone: "good" | "bad" | "neutral"; children: React.ReactNode }) {
  const dot = { good: "bg-accent", bad: "bg-danger", neutral: "bg-muted" }[tone];
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-strip px-3 py-1 font-mono text-xs text-muted">
      <span aria-hidden className={`size-1.5 rounded-full ${dot}`} />
      {children}
    </span>
  );
}
