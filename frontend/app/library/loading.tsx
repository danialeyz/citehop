import { Skeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading articles">
      <Skeleton className="mb-3 h-3 w-24" />
      <Skeleton className="mb-8 h-10 w-72 max-w-full" />
      <Skeleton className="mb-6 h-24 w-full" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-40" />)}
      </div>
    </div>
  );
}
