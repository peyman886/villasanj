import { Inbox, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** Placeholder for content that is still loading; hidden from assistive technology. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-control bg-sand-200", className)}
    />
  );
}

/** Nothing to show, with one clear next action. */
export function EmptyState({
  title,
  children,
  action,
  icon,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center rounded-card border border-dashed border-line-strong bg-surface px-6 py-10 text-center",
        className,
      )}
    >
      <span className="grid size-12 place-items-center rounded-full bg-sunken text-fg-muted">
        {icon ?? <Inbox aria-hidden="true" className="size-6" />}
      </span>
      <p className="mt-4 font-semibold text-balance">{title}</p>
      {children ? (
        <div className="mt-1 max-w-md text-sm text-pretty text-fg-muted">{children}</div>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/** Something failed; says what still works and what to try. */
export function ErrorState({
  title,
  children,
  action,
  className,
}: {
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center rounded-card border border-rose-200 bg-rose-50 px-6 py-10 text-center",
        className,
      )}
    >
      <span className="grid size-12 place-items-center rounded-full bg-surface text-rose-700">
        <TriangleAlert aria-hidden="true" className="size-6" />
      </span>
      <p className="mt-4 font-semibold text-balance text-rose-950">{title}</p>
      {children ? (
        <div className="mt-1 max-w-md text-sm text-pretty text-rose-900">{children}</div>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
