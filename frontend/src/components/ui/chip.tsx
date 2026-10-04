import { X } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const BASE =
  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm whitespace-nowrap";

/** A filter or fact as a pill; with `removeHref` it becomes a removable filter. */
export function Chip({
  children,
  removeHref,
  removeLabel,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  removeHref?: string;
  removeLabel?: string;
  tone?: "neutral" | "brand" | "caution";
  className?: string;
}) {
  const tones = {
    neutral: "border-line-strong bg-surface text-fg",
    brand: "border-brand-300 bg-brand-50 text-brand-900",
    caution: "border-amber-300 bg-amber-50 text-amber-950",
  }[tone];
  return (
    <span className={cn(BASE, tones, removeHref && "pe-1", className)}>
      {children}
      {removeHref ? (
        <Link
          href={removeHref}
          aria-label={removeLabel}
          className="focus-ring grid size-6 place-items-center rounded-full text-fg-muted transition-colors hover:bg-sand-200 hover:text-fg"
        >
          <X aria-hidden="true" className="size-3.5" />
        </Link>
      ) : null}
    </span>
  );
}

/** A link styled as a chip (example searches, filters to add). */
export function ChipLink({
  href,
  children,
  className,
}: {
  href: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        BASE,
        "focus-ring border-line-strong bg-surface text-fg transition-colors hover:border-brand-400 hover:bg-brand-50",
        className,
      )}
    >
      {children}
    </Link>
  );
}
