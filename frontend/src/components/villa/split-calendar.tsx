"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import {
  WEEKDAYS,
  WEEKDAYS_SHORT,
  addDays,
  dayAria,
  faDayNumber,
  inStay,
  months,
  nextSelection,
  stateOf,
  weekdayIndex,
  type DayState,
  type VillaNight,
} from "@/lib/calendar";
import { cn } from "@/lib/cn";
import { faAge } from "@/lib/listing";
import { faNum, millions } from "@/lib/numbers";
import { PLATFORM_ORDER, toneOf } from "@/lib/platforms";

const MONTHS = 2; // the rest of this Jalali month and the next one

type Props = {
  nights: VillaNight[];
  names: Record<string, string>; // platform -> display name, for the platforms of this villa
  start: string;
  days: number;
  checkIn: string | null;
  checkOut: string | null;
  guests: number;
  nowIso: string;
  compact?: boolean; // the booking card's picker: no prices in the cells
};

/**
 * Each day split top (jabama) and bottom (shab): a filled half is available, a hatched one
 * unavailable, a dashed outline not observed yet; a gold outline around the whole day is a hidden
 * night (free on one platform, unavailable on the other). Arrow keys move between days (RTL:
 * the right arrow goes back a day), Enter or a click picks the check-in and then the check-out,
 * and the booking card re-quotes both platforms for that stay from stored observations.
 */
export function SplitCalendar({
  nights,
  names,
  start,
  days,
  checkIn,
  checkOut,
  guests,
  nowIso,
  compact = false,
}: Props) {
  const router = useRouter();
  const byDay = useMemo(() => new Map(nights.map((n) => [n.night, n])), [nights]);
  const grid = useMemo(() => months(start, days).slice(0, MONTHS), [start, days]);
  const platforms = PLATFORM_ORDER.filter((p) => p in names);
  const last = grid.at(-1)?.weeks.flat().filter(Boolean).at(-1) ?? addDays(start, days - 1);
  const [focus, setFocus] = useState(
    checkIn && checkIn >= start && checkIn <= last ? checkIn : start,
  );
  const [pending, setPending] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const now = useMemo(() => new Date(nowIso), [nowIso]);

  const choose = (day: string) => {
    const next = nextSelection(day, pending);
    setPending(next.pending);
    if (next.range) {
      const q = new URLSearchParams({
        in: next.range[0],
        out: next.range[1],
        guests: String(guests),
      });
      router.push(`?${q}#booking`, { scroll: false });
    }
  };

  const move = (event: KeyboardEvent<HTMLButtonElement>, day: string) => {
    const delta: Record<string, number> = {
      ArrowRight: -1, // RTL: right is the previous day
      ArrowLeft: 1,
      ArrowUp: -7,
      ArrowDown: 7,
    };
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(day);
      return;
    }
    const step = delta[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const target = addDays(day, step);
    if (target < start || target > last) return;
    setFocus(target);
    root.current?.querySelector<HTMLButtonElement>(`[data-day="${target}"]`)?.focus();
  };

  const hidden = nights.filter((n) => n.hidden && n.night >= start && n.night <= last).length;

  return (
    <div ref={root}>
      <Legend platforms={platforms} names={names} hidden={hidden} compact={compact} />
      <p className="sr-only" aria-live="polite">
        {pending ? "روز ورود انتخاب شد؛ حالا روز خروج را انتخاب کنید." : ""}
      </p>
      <div className={cn("mt-3 grid items-start gap-6", !compact && "md:grid-cols-2")}>
        {grid.map((month) => (
          <table key={month.key} className="w-full table-fixed border-separate border-spacing-1">
            <caption className="pb-1 text-start text-sm font-semibold">{month.title}</caption>
            <thead>
              <tr>
                {WEEKDAYS_SHORT.map((d, i) => (
                  <th
                    key={d}
                    scope="col"
                    abbr={WEEKDAYS[i]}
                    className={cn("text-xs font-normal text-fg-muted", i === 6 && "font-semibold")}
                  >
                    {d}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {month.weeks.map((week) => (
                <tr key={week.find(Boolean)}>
                  {week.map((day, i) =>
                    day === null ? (
                      <td key={`blank-${i}`} />
                    ) : (
                      <td key={day} className="p-0">
                        <Day
                          day={day}
                          night={byDay.get(day)}
                          platforms={platforms}
                          names={names}
                          selected={inStay(day, checkIn, checkOut) || day === pending}
                          edge={day === checkIn || day === checkOut || day === pending}
                          focusable={day === focus}
                          compact={compact}
                          now={now}
                          onChoose={() => choose(day)}
                          onKey={(e) => move(e, day)}
                        />
                      </td>
                    ),
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      </div>
    </div>
  );
}

const HALF: Record<DayState, string> = {
  available: "",
  unavailable: "bg-hatch",
  unseen: "border border-dashed border-line-strong bg-surface",
};

function Day({
  day,
  night,
  platforms,
  names,
  selected,
  edge,
  focusable,
  compact,
  now,
  onChoose,
  onKey,
}: {
  day: string;
  night: VillaNight | undefined;
  platforms: string[];
  names: Record<string, string>;
  selected: boolean;
  edge: boolean;
  focusable: boolean;
  compact: boolean;
  now: Date;
  onChoose: () => void;
  onKey: (e: KeyboardEvent<HTMLButtonElement>) => void;
}) {
  const offDay =
    weekdayIndex(day) === 6 || platforms.some((p) => night?.by_platform[p]?.is_holiday);
  return (
    <button
      type="button"
      data-day={day}
      data-hidden-night={night?.hidden ? "" : undefined}
      tabIndex={focusable ? 0 : -1}
      aria-label={dayAria(day, night, names, (iso) => faAge(iso, now))}
      aria-pressed={selected}
      onClick={onChoose}
      onKeyDown={onKey}
      className={cn(
        "focus-ring relative flex w-full flex-col overflow-hidden rounded-md text-start transition-shadow",
        compact ? "h-11" : "h-16",
        night?.hidden ? "ring-2 ring-hidden ring-offset-1" : "ring-1 ring-line",
        selected && "ring-2 ring-brand-800 ring-offset-1",
        edge && "ring-brand-900",
      )}
    >
      <span
        className={cn(
          "absolute end-1 top-0.5 z-10 text-[0.8125rem] leading-none font-semibold tabular-nums",
          offDay ? "text-fg underline decoration-2 underline-offset-2" : "text-fg",
        )}
      >
        {faDayNumber(day)}
      </span>
      {platforms.map((p) => {
        const state = stateOf(night, p);
        const seen = night?.by_platform[p];
        return (
          <span
            key={p}
            aria-hidden="true"
            className={cn(
              "flex flex-1 items-end px-1 pb-0.5 text-[0.6875rem] leading-none tabular-nums",
              state === "available" ? toneOf(p).soft : HALF[state],
            )}
          >
            {!compact && state === "available" && seen?.price
              ? millions(seen.price.low_toman)
              : null}
          </span>
        );
      })}
    </button>
  );
}

function Legend({
  platforms,
  names,
  hidden,
  compact,
}: {
  platforms: string[];
  names: Record<string, string>;
  hidden: number;
  compact: boolean;
}) {
  return (
    <div className="space-y-1">
      <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-fg-muted">
        {platforms.map((p, i) => (
          <li key={p} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cn("h-2 w-4 rounded-sm", toneOf(p).soft)} />
            {i === 0 ? "بالا" : "پایین"}: {names[p]}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2 w-4 rounded-sm bg-hatch ring-1 ring-line" />
          ناموجود
        </li>
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="h-2 w-4 rounded-sm border border-dashed border-line-strong"
          />
          هنوز ندیده‌ایم
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-4 rounded-sm ring-2 ring-hidden" />
          شب پنهان
        </li>
        {compact ? null : <li>عدد هر نیمه: قیمت هر شب به میلیون تومان (از)</li>}
      </ul>
      {hidden > 0 && !compact ? (
        <p className="text-sm">
          <span className="font-semibold">{faNum(hidden)} شب پنهان</span>
          <span className="text-fg-muted">
            {" "}
            در این بازه: در یک پلتفرم ناموجود، در دیگری خالی دیده شده.
          </span>
        </p>
      ) : null}
    </div>
  );
}
