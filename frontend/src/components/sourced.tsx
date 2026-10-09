import type { ReactNode } from "react";

import type { Provenance } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { METHOD_TEXT, faAge, faDateTime, faNumber } from "@/lib/listing";

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600";

/**
 * A number (or claim) whose source opens on click: product rule 1, every value has provenance.
 * Built on the native Popover API: Escape and outside clicks close it, and keyboard focus moves
 * from the button into the card, with no hand-written focus handling.
 */
export function Sourced({
  id,
  provenance,
  now,
  label,
  value,
  sourceName,
  children,
  className,
  quiet = false,
}: {
  id: string;
  provenance: Provenance;
  now: Date;
  label: string; // what the value is, for the card title and screen readers
  value?: string; // the exact value, restated in the card (the button may show it rounded)
  sourceName?: string; // the platform's display name (provenance carries its slug)
  children: ReactNode;
  className?: string;
  quiet?: boolean; // no permanent underline: it shows on hover and focus only (M12, X2)
}) {
  const source = provenance.source;
  const rows: [string, ReactNode][] = [];
  if (value) rows.push(["مقدار", value]);
  rows.push(["نوع", METHOD_TEXT[provenance.method]]);
  if (provenance.note) rows.push(["روش", provenance.note]);
  rows.push([
    "زمان مشاهده",
    `${faDateTime(provenance.observed_at)} (${faAge(provenance.observed_at, now)})`,
  ]);
  if (provenance.oldest_input_at !== provenance.observed_at) {
    rows.push(["قدیمی‌ترین ورودی", faAge(provenance.oldest_input_at, now)]);
  }
  if (provenance.inputs > 0) {
    rows.push(["محاسبه از", `${faNumber(provenance.inputs)} مقدار مشاهده‌شده`]);
  }
  rows.push([
    "منبع",
    source ? (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className={cn("text-accent underline underline-offset-4", FOCUS)}
      >
        صفحه‌ی آگهی در {sourceName ?? source.platform}
      </a>
    ) : provenance.inputs > 0 ? (
      "منبع هر ورودی کنار همان ورودی آمده است"
    ) : (
      "بدون پیوند"
    ),
  ]);
  if (provenance.snapshot_id) {
    rows.push([
      "نسخه‌ی ذخیره‌شده",
      <span key="snapshot" className="font-mono text-xs" dir="ltr">
        {provenance.snapshot_id.slice(0, 8)}
      </span>,
    ]);
  }
  // Only phrasing elements (spans) inside: the card is valid wherever a number appears, even in <p>.
  return (
    <>
      <button
        type="button"
        popoverTarget={id}
        data-sourced=""
        className={cn(
          "cursor-help rounded-sm underline decoration-dotted underline-offset-4",
          quiet
            ? "decoration-transparent hover:decoration-fg-subtle focus-visible:decoration-fg-subtle"
            : "decoration-line-strong hover:decoration-fg-muted",
          FOCUS,
          className,
        )}
      >
        {children}
        <span className="sr-only"> (منبع {label})</span>
      </button>
      <span
        id={id}
        popover="auto"
        role="dialog"
        aria-label={`منبع ${label}`}
        className="m-auto w-[min(24rem,calc(100vw-2rem))] rounded-card border border-line-strong bg-surface p-4 text-start text-sm font-normal text-fg shadow-overlay backdrop:bg-scrim/20"
      >
        <span className="block font-medium text-balance">منبع {label}</span>
        <span className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-pretty">
          {rows.map(([name, content]) => (
            <span key={name} className="contents">
              <span className="text-fg-subtle">{name}</span>
              <span className="tabular-nums">{content}</span>
            </span>
          ))}
        </span>
        <button
          type="button"
          popoverTarget={id}
          popoverTargetAction="hide"
          className={cn(
            "mt-4 rounded-control border border-line-strong px-3 py-1.5 text-sm hover:bg-sunken",
            FOCUS,
          )}
        >
          بستن
        </button>
      </span>
    </>
  );
}
