import { cn } from "@/lib/cn";

export type Bar = {
  label: string;
  value: number;
  display: string;
  tone?: "brand" | "sand" | "caution" | "danger";
};

const FILL = {
  brand: "bg-brand-600",
  sand: "bg-sand-400",
  caution: "bg-amber-400",
  danger: "bg-rose-500",
} as const;

/** Labelled horizontal bars; the numbers are text, the bars only repeat them. */
export function BarList({
  bars,
  max,
  className,
  label,
}: {
  bars: Bar[];
  max?: number;
  className?: string;
  label: string;
}) {
  const top = max ?? Math.max(...bars.map((b) => b.value), 1);
  return (
    <ul aria-label={label} className={cn("space-y-2.5", className)}>
      {bars.map((bar) => (
        <li key={bar.label}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-fg">{bar.label}</span>
            <span className="text-fg-muted tabular-nums">{bar.display}</span>
          </div>
          <div aria-hidden="true" className="mt-1 h-2 overflow-hidden rounded-full bg-sand-100">
            <div
              className={cn("h-full rounded-full", FILL[bar.tone ?? "brand"])}
              style={{ width: `${Math.max(0, Math.min(1, bar.value / top)) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ProgressBar({
  value,
  max,
  label,
  display,
  tone = "brand",
}: {
  value: number;
  max: number;
  label: string;
  display: string;
  tone?: keyof typeof FILL;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span>{label}</span>
        <span className="text-fg-muted tabular-nums">{display}</span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={display}
        className="mt-1 h-2 overflow-hidden rounded-full bg-sand-100"
      >
        <div
          className={cn("h-full rounded-full", FILL[tone])}
          style={{ width: `${Math.max(0, Math.min(1, max ? value / max : 0)) * 100}%` }}
        />
      </div>
    </div>
  );
}
