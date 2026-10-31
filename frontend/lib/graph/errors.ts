// User-facing explanations for graph request failures (docs/API.md error table).
// `blocksTraversal` disables Expand / Path until the user reloads or reimports.
import type { ApiError } from "@/lib/api/client";

export type GraphProblem = {
  kind: "stale" | "rebuilding" | "unavailable" | "timeout" | "not_found" | "invalid" | "unreachable" | "version_changed" | "other";
  title: string;
  message: string;
  blocksTraversal: boolean;
};

export function graphProblem(status: number | null, error: ApiError | null): GraphProblem {
  if (status === null) {
    return { kind: "unreachable", title: "API unreachable", message: "The CiteHop API did not respond. Check that `make api` is running, then retry.", blocksTraversal: true };
  }
  const graph = error?.graph;
  const versions = graph ? ` Imported ${graph.imported_version ?? "nothing"}; MariaDB is at ${graph.source_version ?? "an unknown version"}.` : "";
  switch (error?.error) {
    case "graph_stale":
      return { kind: "stale", title: "Graph projection is stale", message: `Neo4j holds an older corpus snapshot, so traversal is disabled.${versions} Run \`make graph-import\`. Search and Library still work.`, blocksTraversal: true };
    case "graph_rebuilding":
      return { kind: "rebuilding", title: "Graph is rebuilding", message: `A graph import is in progress or did not finish.${versions} Traversal is disabled until it completes.`, blocksTraversal: true };
    case "graph_unavailable":
      return { kind: "unavailable", title: "Graph service unavailable", message: `${error.message} Search and Library do not depend on Neo4j and still work.`, blocksTraversal: true };
    case "graph_timeout":
      return { kind: "timeout", title: "Graph query timed out", message: "Neo4j did not answer within the query time limit. Nothing was added. Try depth 1 or a less connected article.", blocksTraversal: false };
    case "not_found":
      return { kind: "not_found", title: "Article not in the graph", message: "This article is not in the imported graph snapshot.", blocksTraversal: false };
  }
  if (status === 422) {
    return { kind: "invalid", title: "Request rejected", message: error?.message ?? "The API rejected the graph parameters.", blocksTraversal: false };
  }
  return { kind: "other", title: "Graph request failed", message: error?.message ?? `The API answered with HTTP ${status}.`, blocksTraversal: false };
}

export function versionChanged(expected: string, received: string): GraphProblem {
  return {
    kind: "version_changed",
    title: "Graph snapshot changed",
    message: `This view was built from ${expected}, but the API now serves ${received}. Mixing snapshots would show edges that may no longer exist, so nothing was added. Reload the exploration.`,
    blocksTraversal: true,
  };
}
