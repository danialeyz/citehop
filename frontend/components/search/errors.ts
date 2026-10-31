// Maps API failures (docs/API.md "Errors") to fixed, user-facing copy and a recovery action.
import type { ApiError } from "@/lib/api/client";

export type Recovery = "retry" | "keyword" | "clear-filters" | "search-again" | "wait";
export type Failure = { title: string; message: string; recovery: Recovery[] };

export function searchFailure(status: number | null, error: ApiError | null): Failure {
  switch (error?.error) {
    case "embedding_mismatch":
      return {
        title: "Meaning search has no matching embeddings",
        message:
          "The stored passages were not embedded with the current query model, so a meaning search would match nothing. Keyword search still works; re-embedding the corpus restores meaning search.",
        recovery: ["keyword"],
      };
    case "embedder_unavailable":
      return {
        title: "The embedding model is not available",
        message: "Meaning search needs the query embedding model on the API server. Keyword search does not.",
        recovery: ["keyword", "retry"],
      };
    case "mariadb_unavailable":
      return {
        title: "The database is unavailable",
        message: "MariaDB did not respond, so no passages could be retrieved. Start the database and try again.",
        recovery: ["retry"],
      };
    case "invalid_request":
      return { title: "These filters cannot be applied", message: error.message, recovery: ["clear-filters"] };
  }
  if (status === 422) return { title: "The search request was rejected", message: "Check the query and filters.", recovery: ["clear-filters"] };
  if (status === null) {
    return { title: "The API is unreachable", message: "The CiteHop API did not respond. Check that it is running, then try again.", recovery: ["retry"] };
  }
  return { title: "Search failed", message: error?.message ?? `The API returned HTTP ${status}.`, recovery: ["retry"] };
}

export function answerFailure(status: number | null, error: ApiError | null): Failure {
  switch (error?.error) {
    case "generation_busy":
      return { title: "Another answer is being generated", message: "Only one answer is generated at a time. Try again when it finishes.", recovery: ["wait"] };
    case "stale_context":
    case "unknown_chunks":
      return {
        title: "These sources are out of date",
        message: "The corpus changed since this search, so these passages cannot be cited. Search again to retrieve current passages.",
        recovery: ["search-again"],
      };
    case "mariadb_unavailable":
      return { title: "The database is unavailable", message: "The cited passages could not be read from MariaDB. Your sources are still shown.", recovery: ["wait"] };
  }
  if (status === null) {
    return { title: "The API is unreachable", message: "No answer was received. Your sources are still shown.", recovery: ["wait"] };
  }
  return { title: "No answer was generated", message: error?.message ?? `The API returned HTTP ${status}.`, recovery: ["wait"] };
}
