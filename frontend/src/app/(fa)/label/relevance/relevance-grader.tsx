"use client";

import { ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { faNumber } from "@/lib/listing";
import { GRADE_TEXT, gradeFor, type RelevanceItem, type RelevanceTask } from "@/lib/reviews";
import { FEATURE_TEXT } from "@/lib/search";

type Grade = 0 | 1 | 2;
const GRADES: Grade[] = [2, 1, 0];
const GRADE_STYLE: Record<Grade, string> = {
  2: "aria-pressed:border-brand-700 aria-pressed:bg-accent-solid aria-pressed:text-white",
  1: "aria-pressed:border-amber-500 aria-pressed:bg-amber-100 aria-pressed:text-amber-950",
  0: "aria-pressed:border-sand-600 aria-pressed:bg-sand-200 aria-pressed:text-fg",
};

function listingHref(key: string): string {
  const [platform, ...id] = key.split(":");
  return `/listings/${platform}/${id.join(":")}`;
}

function toman(value: number | null | undefined): string | null {
  return value === null || value === undefined ? null : `${faNumber(Math.round(value))} تومان`;
}

function range(values: number[] | null | undefined, unit: string): string | null {
  if (!values || values.length < 2) return null;
  const [low, high] = values as [number, number];
  return low === high
    ? `${faNumber(low)} ${unit}`
    : `${faNumber(low)} تا ${faNumber(high)} ${unit}`;
}

function Facts({ item }: { item: RelevanceItem }) {
  const total = toman(item.total_low_toman);
  const facts: [string, string | null][] = [
    ["مکان", item.place || null],
    ["خواب", item.bedrooms === null ? null : faNumber(item.bedrooms)],
    ["ظرفیت", item.max_capacity === null ? null : `${faNumber(item.max_capacity)} نفر`],
    ["جمع اقامت", total ? (item.total_high_toman === null ? `حداقل ${total}` : total) : null],
    ["هر نفر هر شب", toman(item.per_person_night_toman)],
    ["امتیاز", item.rating === null ? null : `${faNumber(Math.round(item.rating * 10) / 10)} از ۵`],
    ["تا ساحل", range(item.coast_m, "متر")],
    ["از تهران", range(item.drive_min, "دقیقه")],
  ];
  return (
    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-4">
      {facts.map(([label, value]) => (
        <div key={label}>
          <dt className="text-xs text-fg-muted">{label}</dt>
          <dd className="tabular-nums">{value ?? "نامشخص"}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Grade every pooled villa 2/1/0; keys grade the selected card and move to the next one. */
export function RelevanceGrader({
  queue,
  labeler,
  task,
}: {
  queue: string;
  labeler: string;
  task: RelevanceTask;
}) {
  const router = useRouter();
  const initial = useMemo(
    () =>
      Object.fromEntries(
        task.items.filter((i) => i.grade !== null).map((i) => [i.listing, i.grade as Grade]),
      ) as Record<string, Grade>,
    [task.items],
  );
  const [grades, setGrades] = useState<Record<string, Grade>>(initial);
  const [active, setActive] = useState(() =>
    Math.max(
      0,
      task.items.findIndex((i) => initial[i.listing] === undefined),
    ),
  );
  const [message, setMessage] = useState("");
  const cards = useRef<(HTMLLIElement | null)[]>([]);
  const graded = Object.keys(grades).length;
  const complete = graded === task.items.length;

  const go = useCallback(
    (position: number) => {
      const params = new URLSearchParams({ queue, labeler, position: String(position) });
      router.push(`/label/relevance?${params}`);
    },
    [router, queue, labeler],
  );

  const grade = useCallback(
    async (index: number, value: Grade) => {
      const item = task.items[index];
      if (!item) return;
      const before = grades[item.listing];
      const next = { ...grades, [item.listing]: value };
      setGrades(next);
      const following = task.items.findIndex((i, j) => j > index && next[i.listing] === undefined);
      const firstOpen = task.items.findIndex((i) => next[i.listing] === undefined);
      const target = following >= 0 ? following : firstOpen >= 0 ? firstOpen : index;
      setActive(target);
      cards.current[target]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      try {
        const response = await fetch("/api/relevance", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            queue,
            labeler,
            position: task.position,
            listing: item.listing,
            grade: value,
          }),
        });
        if (!response.ok) throw new Error(String(response.status));
        setMessage("");
      } catch {
        setGrades((current) => {
          const reverted = { ...current };
          if (before === undefined) delete reverted[item.listing];
          else reverted[item.listing] = before;
          return reverted;
        });
        setMessage(`رأی «${item.title}» ثبت نشد. دوباره امتحان کنید.`);
      }
    },
    [grades, task, queue, labeler],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest("textarea, input")) return;
      const value = gradeFor(event);
      if (value !== null) {
        event.preventDefault();
        void grade(active, value);
      } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const next = Math.max(
          0,
          Math.min(task.items.length - 1, active + (event.key === "ArrowDown" ? 1 : -1)),
        );
        setActive(next);
        cards.current[next]?.scrollIntoView({ block: "nearest" });
      }
    }
    window.addEventListener("keydown", onKey);
    document.documentElement.dataset.reviewKeys = "on"; // the keyboard works from here on
    return () => {
      window.removeEventListener("keydown", onKey);
      delete document.documentElement.dataset.reviewKeys;
    };
  }, [active, grade, task.items.length]);

  return (
    <section aria-labelledby="pool-title" className="mt-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="pool-title" className="font-semibold">
          ویلاها
        </h2>
        <span className="text-sm text-fg-muted tabular-nums">
          {faNumber(graded)} از {faNumber(task.items.length)} داوری شده
        </span>
        <span className="flex-1" />
        <Button variant="ghost" disabled={task.position <= 1} onClick={() => go(task.position - 1)}>
          پرسش قبلی
        </Button>
        <Button
          variant={complete ? "primary" : "ghost"}
          disabled={task.position >= task.total}
          onClick={() => go(task.position + 1)}
        >
          پرسش بعدی
        </Button>
      </div>
      <p role="status" className="mt-2 min-h-5 text-sm text-fg">
        {complete ? "همه‌ی ویلاهای این پرسش داوری شد." : message}
      </p>
      <ol className="mt-2 space-y-3">
        {task.items.map((item, index) => {
          const current = grades[item.listing];
          return (
            <li
              key={item.listing}
              ref={(node) => {
                cards.current[index] = node;
              }}
              className={cn(
                "scroll-mt-28 rounded-card border bg-surface p-4 transition-shadow",
                index === active ? "border-brand-500 shadow-float" : "border-line shadow-raised",
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <a
                    href={item.villa ? `/villas/${item.villa}` : listingHref(item.listing)}
                    target="_blank"
                    rel="noreferrer"
                    className="focus-ring inline-flex items-center gap-1 rounded-sm font-semibold text-balance hover:text-accent"
                  >
                    {item.title}
                    <ExternalLink aria-hidden="true" className="size-3.5 shrink-0" />
                  </a>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {item.features.map((f) => (
                      <Badge key={f} tone="verified">
                        {FEATURE_TEXT[f] ?? f}
                      </Badge>
                    ))}
                    {item.other_platforms.length ? (
                      <Badge tone="info">روی پلتفرم دیگر هم هست</Badge>
                    ) : null}
                  </div>
                </div>
                <div
                  role="group"
                  aria-label={`مرتبط‌بودن «${item.title}»`}
                  className="flex shrink-0 gap-1.5"
                >
                  {GRADES.map((value) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={current === value}
                      onClick={() => {
                        void grade(index, value);
                      }}
                      className={cn(
                        "focus-ring h-9 rounded-control border border-line-strong bg-surface px-3 text-sm font-medium hover:bg-sunken",
                        GRADE_STYLE[value],
                      )}
                    >
                      {GRADE_TEXT[value]}{" "}
                      <kbd className="ms-1 text-xs opacity-70">{faNumber(value)}</kbd>
                    </button>
                  ))}
                </div>
              </div>
              <Facts item={item} />
            </li>
          );
        })}
      </ol>
    </section>
  );
}
