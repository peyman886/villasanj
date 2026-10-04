import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export type Tone = "neutral" | "brand" | "verified" | "caution" | "danger" | "info" | "muted";

const TONES: Record<Tone, string> = {
  neutral: "bg-sand-100 text-sand-800 ring-sand-300",
  brand: "bg-brand-50 text-brand-800 ring-brand-200",
  verified: "bg-brand-50 text-brand-800 ring-brand-300",
  caution: "bg-amber-50 text-amber-900 ring-amber-300",
  danger: "bg-rose-50 text-rose-800 ring-rose-300",
  info: "bg-sky-50 text-sky-900 ring-sky-300",
  muted: "bg-surface text-fg-muted ring-line",
};

const DOTS: Record<Tone, string> = {
  neutral: "bg-sand-500",
  brand: "bg-brand-600",
  verified: "bg-brand-600",
  caution: "bg-amber-500",
  danger: "bg-rose-600",
  info: "bg-sky-600",
  muted: "bg-sand-400",
};

/** A short label with a meaning; the text carries it, the colour only repeats it. */
export function Badge({
  tone = "neutral",
  dot = false,
  icon,
  children,
  className,
}: {
  tone?: Tone;
  dot?: boolean;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {dot ? <span aria-hidden="true" className={cn("size-1.5 rounded-full", DOTS[tone])} /> : null}
      {icon}
      {children}
    </span>
  );
}
