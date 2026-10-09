import type { Interval } from "@/lib/artifacts";
import { cn } from "@/lib/cn";
import { formatFor } from "@/lib/format";
import type { Locale } from "@/lib/i18n";

export type IntervalRow = { label: string; interval: Interval | null; highlight?: boolean };

const TICKS = [0, 0.25, 0.5, 0.75, 1];

/**
 * Estimates with their 95% intervals on a 0–100% axis (precision and recall of policies, H4
 * shares). An optional dashed line marks a bar to clear (e.g. 92% for precision's lower bound).
 * The numbers are written next to each row; the plot repeats them for the eye.
 */
export function IntervalChart({
  rows,
  label,
  min = 0,
  max = 1,
  bar,
  barLabel,
  locale = "fa",
}: {
  rows: IntervalRow[];
  label: string;
  min?: number;
  max?: number;
  bar?: number;
  barLabel?: string;
  locale?: Locale;
}) {
  const pos = (v: number) => `${((Math.max(min, Math.min(max, v)) - min) / (max - min)) * 100}%`;
  return (
    <figure className="rounded-card border border-line bg-surface p-4">
      <figcaption className="sr-only">{label}</figcaption>
      <ul className="space-y-3">
        {rows.map((row) => {
          const i = row.interval;
          return (
            <li
              key={row.label}
              className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[12rem_minmax(0,1fr)_11rem]"
            >
              <span className={cn("text-sm", row.highlight ? "font-semibold" : "text-fg")}>
                {row.label}
              </span>
              <div dir="ltr" aria-hidden="true" className="relative h-5">
                <div className="absolute inset-x-0 top-1/2 h-px bg-sand-200" />
                {TICKS.map((t) => (
                  <div
                    key={t}
                    className="absolute inset-y-0 w-px bg-sand-100"
                    style={{ left: pos(min + t * (max - min)) }}
                  />
                ))}
                {bar !== undefined ? (
                  <div
                    className="absolute -inset-y-1.5 border-l border-dashed border-amber-500"
                    style={{ left: pos(bar) }}
                  />
                ) : null}
                {i && i.estimate !== null ? (
                  <>
                    <div
                      className={cn(
                        "absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full",
                        row.highlight ? "bg-brand-300" : "bg-sand-300",
                      )}
                      style={{ left: pos(i.low), right: `calc(100% - ${pos(i.high)})` }}
                    />
                    <div
                      className={cn(
                        "absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface",
                        row.highlight ? "bg-brand-700" : "bg-sand-600",
                      )}
                      style={{ left: pos(i.estimate) }}
                    />
                  </>
                ) : null}
              </div>
              <span className="text-xs text-fg-muted tabular-nums sm:text-end">
                {formatFor(locale).interval(i)}
              </span>
            </li>
          );
        })}
      </ul>
      <div
        className="mt-2 grid gap-x-4 sm:grid-cols-[12rem_minmax(0,1fr)_11rem]"
        aria-hidden="true"
      >
        <span className="hidden sm:block" />
        <div dir="ltr" className="relative h-4 text-[11px] text-fg-muted">
          {TICKS.map((t) => (
            <span
              key={t}
              className="absolute -translate-x-1/2 tabular-nums"
              style={{ left: pos(min + t * (max - min)) }}
            >
              {Math.round((min + t * (max - min)) * 100)}%
            </span>
          ))}
        </div>
      </div>
      {bar !== undefined && barLabel ? (
        <p className="mt-2 flex items-center gap-2 text-xs text-fg-muted">
          <span aria-hidden="true" className="h-3 border-l border-dashed border-amber-500" />
          {barLabel}
        </p>
      ) : null}
    </figure>
  );
}
