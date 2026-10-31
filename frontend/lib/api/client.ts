// The one CiteHop API client. Types come from schema.d.ts, generated from FastAPI's OpenAPI
// document (`make api-types`); never hand-write request or response shapes.
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type Schemas = components["schemas"];
export type ApiError = Schemas["ErrorBody"];

// Browser: same-origin `/api/*`, proxied to FastAPI by next.config.ts.
// Server rendering: relative URLs do not work, so call the upstream directly.
function baseUrl(): string {
  if (typeof window !== "undefined") return "";
  return process.env.API_UPSTREAM ?? "http://127.0.0.1:8000";
}

export const api = createClient<paths>({ baseUrl: baseUrl() });

// For <a download> links; the browser fetches the CSV through the same proxy.
export function runExportUrl(runId: string): string {
  return `/api/v1/runs/${encodeURIComponent(runId)}/export`;
}

export function isApiError(value: unknown): value is ApiError {
  return typeof value === "object" && value !== null && "error" in value && "message" in value;
}
