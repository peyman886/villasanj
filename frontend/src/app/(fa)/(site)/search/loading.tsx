import { Skeleton } from "@/components/ui/states";

export default function SearchLoading() {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8 pb-16 sm:px-6" role="status">
      <span className="sr-only">در حال جستجو…</span>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="mt-3 h-5 w-96 max-w-full" />
      <Skeleton className="mt-5 h-14 max-w-3xl" />
      <div className="mt-5 flex gap-2">
        <Skeleton className="h-8 w-24 rounded-full" />
        <Skeleton className="h-8 w-32 rounded-full" />
        <Skeleton className="h-8 w-20 rounded-full" />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex gap-4 rounded-card border border-line bg-surface p-4">
              <Skeleton className="h-28 w-40 shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-4 w-1/3" />
              </div>
            </div>
          ))}
        </div>
        <Skeleton className="hidden h-40 lg:block" />
      </div>
    </div>
  );
}
