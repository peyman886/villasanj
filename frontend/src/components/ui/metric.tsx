import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * One number that matters, with what it means and where it comes from. The value is the visual
 * anchor; the label says what it is; `source` is a provenance chip or a link to the evidence.
 */
export function MetricCard({
  label,
  value,
  detail,
  source,
  tone = "neutral",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  detail?: ReactNode;
  source?: ReactNode;
  tone?: "neutral" | "verified" | "caution" | "danger";
  className?: string;
}) {
  const accent = {
    neutral: "before:bg-sand-300",
    verified: "before:bg-brand-500",
    caution: "before:bg-amber-400",
    danger: "before:bg-rose-500",
  }[tone];
  return (
    <div
      className={cn(
        "relative flex flex-col overflow-hidden rounded-card border border-line bg-surface p-4 shadow-raised",
        "before:absolute before:inset-y-0 before:start-0 before:w-1",
        accent,
        className,
      )}
    >
      <p className="text-sm text-fg-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-fg">{value}</p>
      {detail ? <p className="mt-1 text-sm text-pretty text-fg-muted">{detail}</p> : null}
      {source ? <div className="mt-auto pt-3">{source}</div> : null}
    </div>
  );
}

export function MetricGrid({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-4", className)}>{children}</div>
  );
}
