import Link from "next/link";

import { ErrorState, buttonSecondary } from "@/components/ui";
import type { ApiError } from "@/lib/api/client";

/** Explains a failed API call using the server's safe message; never shows raw exceptions. */
export function LoadError({ status, error, retryHref }: { status: number | null; error: ApiError | null; retryHref: string }) {
  const title =
    status === null
      ? "The CiteHop API is unreachable"
      : error?.error === "mariadb_unavailable"
        ? "MariaDB is unavailable"
        : "The Library could not be loaded";
  const detail =
    status === null
      ? "Start the API with make api, then retry."
      : (error?.message ?? `The API answered with HTTP ${status}.`);
  return (
    <ErrorState title={title} action={<Link href={retryHref} className={buttonSecondary}>Retry</Link>}>
      <p>{detail}</p>
    </ErrorState>
  );
}
