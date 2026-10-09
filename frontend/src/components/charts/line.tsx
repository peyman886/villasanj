import { cn } from "@/lib/cn";
import { t as tr, type Locale } from "@/lib/i18n";

export type Point = { x: number; y: number | null; low?: number; high?: number };
export type Series = { label: string; points: Point[]; tone: "brand" | "amber" | "sand" };

const STROKE = {
  brand: "stroke-brand-700",
  amber: "stroke-amber-500",
  sand: "stroke-sand-500",
} as const;
const BAND = { brand: "fill-brand-200", amber: "fill-amber-200", sand: "fill-sand-200" } as const;
const SWATCH = { brand: "bg-brand-700", amber: "bg-amber-500", sand: "bg-sand-500" } as const;

const W = 640;
const H = 260;
const PAD = { top: 12, right: 12, bottom: 32, left: 40 };

/**
 * A 0–1 line chart over a numeric x (e.g. precision and recall against the rule threshold), with
 * optional 95% bands and a marker at a chosen x. Plotted left to right like any numeric axis;
 * the legend and the data table are in the page's language and readable without the picture.
 */
export function LineChart({
  series,
  label,
  xLabel,
  marker,
  formatX = (x) => String(x),
  formatY = (y) => `${Math.round(y * 1000) / 10}%`,
  locale = "fa",
}: {
  series: Series[];
  label: string;
  xLabel: string;
  marker?: { x: number; label: string };
  formatX?: (x: number) => string;
  formatY?: (y: number) => string;
  locale?: Locale;
}) {
  const xs = series.flatMap((s) => s.points.map((p) => p.x));
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const px = (x: number) =>
    PAD.left + ((x - xMin) / (xMax - xMin || 1)) * (W - PAD.left - PAD.right);
  const py = (y: number) => PAD.top + (1 - y) * (H - PAD.top - PAD.bottom);
  const yTicks = [0, 0.25, 0.5, 0.75, 1];
  const xTicks = Array.from(new Set(xs.filter((x) => Number.isInteger(x))));
  return (
    <figure className="rounded-card border border-line bg-surface p-4">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="ltr w-full">
        {yTicks.map((t) => (
          <g key={t}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={py(t)}
              y2={py(t)}
              className="stroke-sand-200"
            />
            <text
              x={PAD.left - 6}
              y={py(t) + 4}
              textAnchor="end"
              className="fill-fg-muted text-[11px]"
            >
              {Math.round(t * 100)}%
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text
            key={t}
            x={px(t)}
            y={H - PAD.bottom + 16}
            textAnchor="middle"
            className="fill-fg-muted text-[11px]"
          >
            {formatX(t)}
          </text>
        ))}
        <text
          x={(W + PAD.left) / 2}
          y={H - 4}
          textAnchor="middle"
          className="fill-fg-muted text-[11px]"
        >
          {xLabel}
        </text>
        {series.map((s) => {
          const banded = s.points.filter(
            (p) => p.low !== undefined && p.high !== undefined && p.y !== null,
          );
          if (banded.length < 2) return null;
          const top = banded.map((p) => `${px(p.x)},${py(p.high ?? 0)}`);
          const bottom = [...banded].reverse().map((p) => `${px(p.x)},${py(p.low ?? 0)}`);
          return (
            <polygon
              key={`${s.label}-band`}
              points={[...top, ...bottom].join(" ")}
              className={cn(BAND[s.tone])}
              opacity={0.45}
            />
          );
        })}
        {series.map((s) => {
          const path = s.points
            .filter((p) => p.y !== null)
            .map((p, i) => `${i === 0 ? "M" : "L"}${px(p.x)},${py(p.y ?? 0)}`)
            .join(" ");
          return (
            <path
              key={s.label}
              d={path}
              fill="none"
              strokeWidth={2.25}
              className={STROKE[s.tone]}
            />
          );
        })}
        {marker ? (
          <g>
            <line
              x1={px(marker.x)}
              x2={px(marker.x)}
              y1={PAD.top}
              y2={H - PAD.bottom}
              strokeDasharray="4 3"
              className="stroke-fg"
              strokeWidth={1.25}
            />
            <text
              x={px(marker.x) + 5}
              y={PAD.top + 10}
              className="fill-fg text-[11px] font-semibold"
            >
              {marker.label}
            </text>
          </g>
        ) : null}
      </svg>
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-muted">
        {series.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("h-0.5 w-4 rounded-full", SWATCH[s.tone])} />
            {s.label}
          </span>
        ))}
        <span>
          {tr(locale, "نوار کم‌رنگ: بازه‌ی اطمینان ۹۵٪", "Shaded band: 95% confidence interval")}
        </span>
      </figcaption>
      <details className="mt-2 text-xs">
        <summary className="focus-ring w-fit cursor-pointer rounded-sm text-accent">
          {tr(locale, "داده‌های نمودار", "Chart data")}
        </summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <table className="w-full text-start tabular-nums">
            <thead className="text-fg-muted">
              <tr>
                <th scope="col" className="p-1 text-start font-medium">
                  {xLabel}
                </th>
                {series.map((s) => (
                  <th key={s.label} scope="col" className="p-1 text-start font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(series[0]?.points ?? []).map((p, index) => (
                <tr key={p.x} className="border-t border-line">
                  <td className="p-1">{formatX(p.x)}</td>
                  {series.map((s) => {
                    const v = s.points[index]?.y;
                    return (
                      <td key={s.label} className="p-1">
                        {v === null || v === undefined ? "-" : formatY(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
