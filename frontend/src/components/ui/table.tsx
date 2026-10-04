import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** A data table that scrolls sideways inside its card on narrow screens, never the page. */
export function DataTable({
  caption,
  children,
  className,
  minWidth = "32rem",
}: {
  caption?: ReactNode;
  children: ReactNode;
  className?: string;
  minWidth?: string;
}) {
  return (
    <div
      className={cn("overflow-x-auto rounded-card border border-line bg-surface", className)}
      tabIndex={0}
      role="region"
      aria-label={typeof caption === "string" ? caption : undefined}
    >
      <table
        style={{ minWidth }}
        className="w-full text-start text-sm tabular-nums [&_td]:px-3 [&_td]:py-2.5 [&_th]:px-3 [&_th]:py-2.5 [&_th]:text-start [&_th]:font-medium [&_thead]:bg-sunken [&_thead]:text-fg-muted [&_tbody_tr]:border-t [&_tbody_tr]:border-line"
      >
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}
