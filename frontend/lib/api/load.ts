// Normalizes openapi-fetch results and network failures for server components,
// so pages render explicit error states instead of throwing.
import { isApiError, type ApiError } from "./client";

export type Loaded<T> =
  | { ok: true; data: T }
  | { ok: false; status: number | null; error: ApiError | null };

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

export async function load<T>(call: () => Promise<FetchResult<T>>): Promise<Loaded<T>> {
  try {
    const { data, error, response } = await call();
    if (data !== undefined) return { ok: true, data };
    return { ok: false, status: response.status, error: isApiError(error) ? error : null };
  } catch {
    return { ok: false, status: null, error: null }; // API unreachable
  }
}
