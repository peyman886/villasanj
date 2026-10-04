import { CircleAlert, Info, OctagonAlert, ShieldCheck, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Kind = "info" | "caution" | "danger" | "verified" | "degraded";

const STYLES: Record<Kind, { box: string; icon: string; Icon: typeof Info }> = {
  info: { box: "border-sky-200 bg-sky-50 text-sky-950", icon: "text-sky-700", Icon: Info },
  caution: {
    box: "border-amber-200 bg-amber-50 text-amber-950",
    icon: "text-amber-700",
    Icon: CircleAlert,
  },
  danger: {
    box: "border-rose-200 bg-rose-50 text-rose-950",
    icon: "text-rose-700",
    Icon: OctagonAlert,
  },
  verified: {
    box: "border-brand-200 bg-brand-50 text-brand-950",
    icon: "text-brand-700",
    Icon: ShieldCheck,
  },
  degraded: {
    box: "border-sand-300 bg-sunken text-fg",
    icon: "text-fg-muted",
    Icon: WifiOff,
  },
};

/** A boxed note with a meaning; `role="status"` only where it announces a change. */
export function Callout({
  kind = "info",
  title,
  children,
  className,
  live = false,
}: {
  kind?: Kind;
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
  live?: boolean;
}) {
  const style = STYLES[kind];
  return (
    <div
      role={live ? "status" : undefined}
      className={cn("flex gap-3 rounded-card border p-4 text-sm", style.box, className)}
    >
      <style.Icon aria-hidden="true" className={cn("mt-0.5 size-5 shrink-0", style.icon)} />
      <div className="min-w-0 text-pretty">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className={cn(title && "mt-1", "space-y-2")}>{children}</div> : null}
      </div>
    </div>
  );
}
