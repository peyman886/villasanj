"use client";

import {
  Binoculars,
  Droplets,
  Flame,
  FlameKindling,
  Layers,
  Minus,
  Plus,
  SlidersHorizontal,
  SquareParking,
  Star,
  Trash2,
  Trees,
  Waves,
  WavesLadder,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";
import {
  FEATURES,
  PLATFORMS,
  PROPERTY_TYPES,
  RATINGS,
  SEA_DISTANCES,
  activeCount,
  filterParams,
  histogram,
  villasPassing,
  type Facet,
  type Filters,
} from "@/lib/filters";
import { distance, faNum, shortAmount } from "@/lib/numbers";
import { FEATURE_TEXT } from "@/lib/search";

const FEATURE_ICON: Record<string, LucideIcon> = {
  pool: WavesLadder,
  jacuzzi: Droplets,
  near_sea: Waves,
  sea_view: Binoculars,
  forest: Trees,
  fireplace: FlameKindling,
  parking: SquareParking,
  barbecue: Flame,
};

const FILTER_KEYS = [
  "pmin",
  "pmax",
  "pn",
  "rooms",
  "cap",
  "amen",
  "type",
  "plat",
  "both",
  "instant",
  "rating",
  "sea",
];

type Load = { state: "idle" | "loading" | "error" } | { state: "ready"; rows: Facet[] };

/**
 * The filter panel (M12, after HomeToGo's and jabama's): quick tiles, the price spread, rooms and
 * capacity, amenities, property type, platform, rating and the distance to the sea, with a live
 * «نمایش N ویلا». The count is computed here from the query's ranked listings (the same rules as
 * the server); applying the filters reloads the results, which the server filters.
 */
export function FilterPanel({
  query,
  drop,
  area,
  current,
}: {
  query: string;
  drop: string[];
  area: number[] | null;
  current: Filters;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [draft, setDraft] = useState<Filters>(current);
  const [load, setLoad] = useState<Load>({ state: "idle" });
  const active = activeCount(current);

  const open = useCallback(async () => {
    setDraft(current);
    dialog.current?.showModal();
    if (load.state === "ready" || load.state === "loading") return;
    setLoad({ state: "loading" });
    try {
      const response = await fetch("/api/search-facets", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ query, drop, ...(area ? { area } : {}) }),
      });
      if (!response.ok) throw new Error(String(response.status));
      setLoad({ state: "ready", rows: (await response.json()) as Facet[] });
    } catch {
      setLoad({ state: "error" });
    }
  }, [area, current, drop, load.state, query]);

  const rows = load.state === "ready" ? load.rows : null;
  const count = rows ? villasPassing(rows, draft) : null;
  const set = (patch: Filters) => setDraft((d) => ({ ...d, ...patch }));
  const toggle = (field: "features" | "property_types" | "platforms", value: string) =>
    setDraft((d) => {
      const list = d[field] ?? [];
      return {
        ...d,
        [field]: list.includes(value) ? list.filter((x) => x !== value) : [...list, value],
      };
    });
  const countFor = (patch: Filters) => (rows ? villasPassing(rows, { ...draft, ...patch }) : null);

  const apply = () => {
    const next = new URLSearchParams(params.toString());
    for (const key of FILTER_KEYS) next.delete(key);
    for (const [key, value] of filterParams(draft)) next.set(key, value);
    dialog.current?.close();
    router.push(`${pathname}?${next}`, { scroll: false });
  };

  return (
    <>
      <button
        type="button"
        onClick={open}
        data-filter-button=""
        className={cn(
          "focus-ring inline-flex h-9 items-center gap-2 rounded-full border px-3.5 text-sm font-medium transition-colors active:scale-[0.98]",
          active
            ? "border-brand-700 bg-brand-50 text-brand-900"
            : "border-line-strong bg-surface text-fg hover:border-sand-500",
        )}
      >
        <SlidersHorizontal aria-hidden="true" className="size-4" />
        فیلترها
        {active ? (
          <span className="grid size-5 place-items-center rounded-full bg-accent-solid text-xs text-white tabular-nums">
            {faNum(active)}
          </span>
        ) : null}
      </button>
      <dialog
        ref={dialog}
        aria-labelledby="filters-title"
        className="m-auto h-dvh max-h-none w-full max-w-none overflow-hidden bg-surface p-0 text-fg backdrop:bg-scrim/40 open:flex open:animate-fade-in open:flex-col sm:h-auto sm:max-h-[88dvh] sm:max-w-2xl sm:rounded-modal sm:shadow-overlay"
      >
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 id="filters-title" className="text-lg font-bold">
            فیلترها
          </h2>
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            aria-label="بستن فیلترها"
            className="focus-ring grid size-9 place-items-center rounded-full hover:bg-sunken"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto overscroll-contain px-5 py-6">
          <Group title="فیلترهای سریع">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <Tile
                icon={Layers}
                label="در هر دو پلتفرم"
                pressed={draft.multi_platform ?? false}
                count={countFor({ multi_platform: true })}
                onClick={() => set({ multi_platform: draft.multi_platform ? undefined : true })}
              />
              <Tile
                icon={Zap}
                label="رزرو آنی"
                pressed={draft.instant ?? false}
                count={countFor({ instant: true })}
                onClick={() => set({ instant: draft.instant ? undefined : true })}
              />
              {(["pool", "near_sea", "forest", "jacuzzi"] as const).map((f) => (
                <Tile
                  key={f}
                  icon={FEATURE_ICON[f] ?? Waves}
                  label={FEATURE_TEXT[f] ?? f}
                  pressed={(draft.features ?? []).includes(f)}
                  count={countFor({ features: [...new Set([...(draft.features ?? []), f])] })}
                  onClick={() => toggle("features", f)}
                />
              ))}
            </div>
          </Group>

          <Group title="قیمت">
            <PriceFilter draft={draft} rows={rows} set={set} />
          </Group>

          <Group title="اتاق و ظرفیت">
            <div className="divide-y divide-line">
              <Stepper
                label="اتاق خواب"
                value={draft.bedrooms_min}
                max={10}
                onChange={(v) => set({ bedrooms_min: v })}
              />
              <Stepper
                label="ظرفیت"
                unit="نفر"
                value={draft.capacity_min}
                max={30}
                onChange={(v) => set({ capacity_min: v })}
              />
            </div>
          </Group>

          <Group title="امکانات" hint="آنچه خود آگهی نوشته، یا نقشه و عکس‌ها نشان می‌دهند">
            <CheckGrid
              items={FEATURES.map((f) => ({
                value: f,
                label: FEATURE_TEXT[f] ?? f,
                icon: FEATURE_ICON[f],
                checked: (draft.features ?? []).includes(f),
                count: countFor({ features: [...new Set([...(draft.features ?? []), f])] }),
              }))}
              onToggle={(v) => toggle("features", v)}
            />
          </Group>

          <Group title="نوع اقامتگاه">
            <CheckGrid
              items={PROPERTY_TYPES.map(([value, label]) => ({
                value,
                label,
                checked: (draft.property_types ?? []).includes(value),
                count: countFor({ property_types: [value] }),
              }))}
              onToggle={(v) => toggle("property_types", v)}
            />
          </Group>

          <Group title="پلتفرم">
            <ChoiceRow
              label="پلتفرم"
              options={[
                { key: "all", text: "همه" },
                ...PLATFORMS.map(([k, t]) => ({ key: k, text: `فقط ${t}` })),
              ]}
              selected={draft.platforms?.length === 1 ? (draft.platforms[0] ?? "all") : "all"}
              onSelect={(k) => set({ platforms: k === "all" ? undefined : [k] })}
            />
          </Group>

          <Group title="امتیاز مهمان‌ها">
            <ChoiceRow
              label="امتیاز"
              icon={<Star aria-hidden="true" className="size-3.5 fill-amber-400 text-amber-500" />}
              options={[
                { key: "all", text: "همه" },
                ...RATINGS.map((r) => ({ key: String(r), text: `${faNum(r, 1)} به بالا` })),
              ]}
              selected={draft.rating_min !== undefined ? String(draft.rating_min) : "all"}
              onSelect={(k) => set({ rating_min: k === "all" ? undefined : Number(k) })}
            />
          </Group>

          <Group
            title="فاصله تا دریا"
            hint="فاصله‌ی خط مستقیم تا ساحل، از نزدیک‌ترین نقطه‌ای که ویلا ممکن است باشد"
          >
            <ChoiceRow
              label="فاصله تا دریا"
              options={[
                { key: "all", text: "همه" },
                ...SEA_DISTANCES.map((m) => ({ key: String(m), text: `تا ${distance(m)}` })),
              ]}
              selected={draft.coast_max_m !== undefined ? String(draft.coast_max_m) : "all"}
              onSelect={(k) => set({ coast_max_m: k === "all" ? undefined : Number(k) })}
            />
          </Group>
        </div>

        <footer className="flex items-center justify-between gap-3 border-t border-line px-5 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            onClick={() => setDraft({})}
            disabled={activeCount(draft) === 0}
            className="focus-ring inline-flex h-11 items-center gap-1.5 rounded-control px-3 text-sm font-medium text-fg-muted hover:bg-sunken hover:text-fg disabled:opacity-40"
          >
            <Trash2 aria-hidden="true" className="size-4" />
            حذف همه
          </button>
          <button
            type="button"
            onClick={apply}
            disabled={count === 0}
            data-apply-filters=""
            className="focus-ring inline-flex h-11 min-w-48 items-center justify-center rounded-control bg-brand-gradient px-6 font-semibold text-white shadow-raised transition-transform hover:opacity-95 active:scale-[0.98] disabled:bg-none disabled:bg-sand-300 disabled:text-fg-muted"
          >
            <span aria-live="polite">
              {load.state === "error"
                ? "اعمال فیلترها"
                : count === null
                  ? "در حال شمردن…"
                  : count === 0
                    ? "ویلایی با این فیلترها نیست"
                    : `نمایش ${faNum(count)} ویلا`}
            </span>
          </button>
        </footer>
      </dialog>
    </>
  );
}

function Group({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="border-t border-line pt-6 first:border-t-0 first:pt-0">
      <h3 className="font-bold">{title}</h3>
      {hint ? <p className="mt-0.5 text-sm text-fg-muted">{hint}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Tile({
  icon: Icon,
  label,
  pressed,
  count,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  pressed: boolean;
  count: number | null;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      data-quick-filter=""
      className={cn(
        "focus-ring flex min-h-16 items-center gap-3 rounded-card border px-3 py-2.5 text-start text-sm transition-[border-color,background-color,box-shadow] duration-150 active:scale-[0.98]",
        pressed
          ? "border-brand-700 bg-brand-50 text-brand-900 ring-1 ring-brand-700"
          : "border-line bg-surface text-fg hover:border-line-strong hover:bg-sunken/60",
        count === 0 && !pressed && "text-fg-muted opacity-60",
      )}
    >
      <span
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-full",
          pressed ? "bg-accent-solid text-white" : "bg-sunken text-fg-muted",
        )}
      >
        <Icon aria-hidden="true" className="size-[1.125rem]" />
      </span>
      <span className="min-w-0">
        <span className="block leading-tight font-semibold">{label}</span>
        <span className="mt-0.5 block h-4 text-xs text-fg-muted tabular-nums">
          {count !== null ? `${faNum(count)} ویلا` : ""}
        </span>
      </span>
    </button>
  );
}

function Stepper({
  label,
  unit,
  value,
  max,
  onChange,
}: {
  label: string;
  unit?: string;
  value: number | undefined;
  max: number;
  onChange: (v: number | undefined) => void;
}) {
  const text =
    value === undefined ? "مهم نیست" : `${faNum(value)}${unit ? ` ${unit}` : ""} به بالا`;
  return (
    <div role="group" aria-label={label} className="flex items-center justify-between gap-3 py-3">
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-sm text-fg-muted" aria-live="polite">
          {text}
        </span>
      </span>
      <span className="flex items-center gap-3">
        <button
          type="button"
          aria-label={`${label}: یکی کمتر`}
          disabled={value === undefined}
          onClick={() => onChange(value === undefined || value <= 1 ? undefined : value - 1)}
          className="focus-ring grid size-9 place-items-center rounded-full border border-line-strong hover:bg-sunken disabled:opacity-35"
        >
          <Minus aria-hidden="true" className="size-4" />
        </button>
        <span className="w-6 text-center font-semibold tabular-nums">
          {value === undefined ? "-" : faNum(value)}
        </span>
        <button
          type="button"
          aria-label={`${label}: یکی بیشتر`}
          disabled={value !== undefined && value >= max}
          onClick={() => onChange(Math.min(max, (value ?? 0) + 1))}
          className="focus-ring grid size-9 place-items-center rounded-full border border-line-strong hover:bg-sunken disabled:opacity-35"
        >
          <Plus aria-hidden="true" className="size-4" />
        </button>
      </span>
    </div>
  );
}

function CheckGrid({
  items,
  onToggle,
}: {
  items: {
    value: string;
    label: string;
    icon?: LucideIcon | undefined;
    checked: boolean;
    count: number | null;
  }[];
  onToggle: (value: string) => void;
}) {
  return (
    <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
      {items.map(({ value, label, icon: Icon, checked, count }) => (
        <li key={value}>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-control px-1 hover:bg-sunken/60">
            {Icon ? <Icon aria-hidden="true" className="size-5 shrink-0 text-fg-muted" /> : null}
            <span className="flex-1">{label}</span>
            {count !== null ? (
              <span className="text-xs text-fg-muted tabular-nums">{faNum(count)}</span>
            ) : null}
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onToggle(value)}
              className="size-5 accent-brand-700"
            />
          </label>
        </li>
      ))}
    </ul>
  );
}

function ChoiceRow({
  label,
  options,
  selected,
  onSelect,
  icon,
}: {
  label: string;
  options: { key: string; text: string }[];
  selected: string;
  onSelect: (key: string) => void;
  icon?: ReactNode;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.key}
          type="button"
          role="radio"
          aria-checked={selected === o.key}
          onClick={() => onSelect(o.key)}
          className={cn(
            "focus-ring inline-flex h-9 items-center gap-1.5 rounded-full border px-3.5 text-sm transition-colors duration-150 active:scale-[0.98]",
            selected === o.key
              ? "border-brand-700 bg-brand-50 font-semibold text-brand-900 ring-1 ring-brand-700"
              : "border-line-strong bg-surface hover:border-sand-500 hover:bg-sunken/60",
          )}
        >
          {o.key !== "all" ? icon : null}
          {o.text}
        </button>
      ))}
    </div>
  );
}

/** Whole stay or per night, the spread of prices, and a two-handle range over it. */
function PriceFilter({
  draft,
  rows,
  set,
}: {
  draft: Filters;
  rows: Facet[] | null;
  set: (patch: Filters) => void;
}) {
  const perNight = draft.per_night ?? false;
  const h = useMemo(() => (rows ? histogram(rows, draft) : null), [rows, draft]);
  const low = draft.price_min ?? h?.min ?? 0;
  const high = draft.price_max ?? h?.max ?? 0;
  const peak = h ? Math.max(1, ...h.bins) : 1;
  const share = (v: number) => (h && h.max > h.min ? ((v - h.min) / (h.max - h.min)) * 100 : 0);
  const flip = (next: boolean) =>
    set({ per_night: next || undefined, price_min: undefined, price_max: undefined });
  return (
    <div>
      <div
        role="radiogroup"
        aria-label="قیمت برای"
        className="inline-flex rounded-full bg-sunken p-1"
      >
        {[
          [false, "کل سفر"],
          [true, "هر شب"],
        ].map(([value, text]) => (
          <button
            key={String(value)}
            type="button"
            role="radio"
            aria-checked={perNight === value}
            onClick={() => flip(value as boolean)}
            className={cn(
              "focus-ring rounded-full px-4 py-1.5 text-sm transition-colors",
              perNight === value ? "bg-surface font-semibold shadow-raised" : "text-fg-muted",
            )}
          >
            {text as string}
          </button>
        ))}
      </div>
      {h ? (
        <div className="mt-4">
          <div aria-hidden="true" className="flex h-16 items-end gap-0.5">
            {h.bins.map((n, i) => {
              const from = h.min + i * h.step;
              const inside = from + h.step > low && from < high;
              return (
                <span
                  key={i}
                  className={cn(
                    "flex-1 rounded-t-sm transition-colors duration-150",
                    inside ? "bg-brand-400" : "bg-sand-200",
                  )}
                  style={{ height: `${Math.max(4, (n / peak) * 100)}%` }}
                />
              );
            })}
          </div>
          <div className="relative h-6">
            <span
              aria-hidden="true"
              className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-sand-300"
            />
            <span
              aria-hidden="true"
              className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-accent-solid"
              style={{
                insetInlineStart: `${share(low)}%`,
                width: `${Math.max(0, share(high) - share(low))}%`,
              }}
            />
            <input
              type="range"
              aria-label="کمترین قیمت"
              min={h.min}
              max={h.max}
              step={h.step / 4}
              value={low}
              onChange={(e) => {
                const v = Math.min(Number(e.target.value), high);
                set({ price_min: v <= h.min ? undefined : v });
              }}
              className="range-thumb pointer-events-none absolute inset-0 w-full appearance-none bg-transparent"
            />
            <input
              type="range"
              aria-label="بیشترین قیمت"
              min={h.min}
              max={h.max}
              step={h.step / 4}
              value={high}
              onChange={(e) => {
                const v = Math.max(Number(e.target.value), low);
                set({ price_max: v >= h.max ? undefined : v });
              }}
              className="range-thumb pointer-events-none absolute inset-0 w-full appearance-none bg-transparent"
            />
          </div>
          <p className="mt-1 flex justify-between text-sm tabular-nums">
            <span>
              از <strong>{shortAmount(low, "lower")}</strong> تومان
            </span>
            {draft.price_max === undefined ? (
              <span>
                <strong>{shortAmount(high, "upper")}</strong> تومان و بیشتر
              </span>
            ) : (
              <span>
                تا <strong>{shortAmount(high, "upper")}</strong> تومان
              </span>
            )}
          </p>
          <p className="mt-2 text-xs text-fg-muted">
            قیمت‌ها بدون کارمزد پلتفرم‌اند؛ فیلتر روی ارزان‌ترین قیمت هر ویلا اعمال می‌شود.
          </p>
        </div>
      ) : (
        <div aria-hidden="true" className="mt-4 h-16 animate-pulse rounded-control bg-sand-100" />
      )}
    </div>
  );
}
