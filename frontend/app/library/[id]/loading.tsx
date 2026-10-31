import { Skeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div role="status" aria-label="Loading article">
      <Skeleton className="mb-6 h-4 w-32" />
      <Skeleton className="mb-3 h-3 w-48" />
      <Skeleton className="mb-5 h-10 w-96 max-w-full" />
      <Skeleton className="mb-8 h-10 w-80 max-w-full" />
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Skeleton className="h-72 lg:col-start-2 lg:row-start-1" />
        <div className="flex flex-col gap-4 lg:col-start-1 lg:row-start-1">
          {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-44" />)}
        </div>
      </div>
    </div>
  );
}
