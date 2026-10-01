"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import {
  LABEL_TEXT,
  LABELS,
  type Label,
  type LabelTask,
  type ListingCard,
  faDistance,
  faNumber,
  faPropertyType,
  shortcutFor,
  type TaskResult,
} from "@/lib/labeling";

type Status = "loading" | "ready" | "done" | "error";
type Lightbox = { card: ListingCard; index: number } | null;

const KEY_HINT: Record<Label, string> = { match: "M", non_match: "N", unsure: "U" };
const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

const ERROR_MESSAGE = "بارگذاری جفت ممکن نشد. API در دسترس است؟ (make up)";

export function LabelingTool({
  queue,
  labeler,
  first,
}: {
  queue: string;
  labeler: string;
  first: TaskResult;
}) {
  const [task, setTask] = useState<LabelTask | null>(first.kind === "ready" ? first.task : null);
  const [status, setStatus] = useState<Status>(first.kind);
  const [message, setMessage] = useState(first.kind === "error" ? ERROR_MESSAGE : "");
  const [saving, setSaving] = useState(false);
  const [lightbox, setLightbox] = useState<Lightbox>(null);
  const startedAt = useRef(0);
  const dialog = useRef<HTMLDialogElement>(null);

  const load = useCallback(
    async (position?: number) => {
      setStatus("loading");
      const params = new URLSearchParams({ queue, labeler });
      if (position !== undefined) params.set("position", String(position));
      let result: TaskResult = { kind: "error" };
      try {
        const response = await fetch(`/api/er/task?${params}`, { cache: "no-store" });
        result = (await response.json()) as TaskResult;
      } catch {
        // reported below
      }
      if (result.kind === "ready") {
        setTask(result.task);
        startedAt.current = performance.now();
        window.scrollTo({ top: 0 });
      } else if (result.kind === "done") {
        setTask(null);
      } else {
        setMessage(ERROR_MESSAGE);
      }
      setStatus(result.kind);
    },
    [queue, labeler],
  );

  const save = useCallback(
    async (label: Label) => {
      if (!task || saving) return;
      setSaving(true);
      const seconds = Math.round((performance.now() - startedAt.current) / 100) / 10;
      try {
        const response = await fetch("/api/er/label", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ queue, pair: task.pair, label, labeler, seconds }),
        });
        if (!response.ok) throw new Error(String(response.status));
        setMessage(`ذخیره شد: ${LABEL_TEXT[label]}`);
        await load();
      } catch {
        setMessage("ذخیره نشد؛ دوباره امتحان کنید.");
      } finally {
        setSaving(false);
      }
    },
    [task, saving, queue, labeler, load],
  );

  const move = useCallback(
    (step: -1 | 1) => {
      if (!task) return;
      const position = task.position + step;
      if (position >= 0 && position < task.total) void load(position);
    },
    [task, load],
  );

  useEffect(() => {
    startedAt.current = performance.now(); // the first pair was rendered on the server
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (dialog.current?.open || status !== "ready") return;
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable]")) return;
      const shortcut = shortcutFor(event);
      if (!shortcut) return;
      event.preventDefault();
      if (shortcut.kind === "label") void save(shortcut.label);
      else move(shortcut.kind === "next" ? 1 : -1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [status, save, move]);

  function openPhoto(card: ListingCard, index: number) {
    setLightbox({ card, index });
    dialog.current?.showModal();
  }

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-4 px-4 pt-6 pb-36">
      <header className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h1 className="text-xl font-bold text-balance">این دو آگهی یک ویلای واقعی‌اند؟</h1>
        {task && (
          <p className="text-sm text-stone-600 tabular-nums">
            جفت {faNumber(task.position + 1)} از {faNumber(task.total)} · برچسب‌خورده{" "}
            {faNumber(task.labeled)}
          </p>
        )}
      </header>

      <p role="status" className="min-h-6 text-sm text-stone-700">
        {message}
      </p>

      {status === "done" && (
        <section className="rounded-xl border border-stone-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-balance">همه‌ی جفت‌های این صف برچسب خوردند</h2>
          <p className="mt-2 text-stone-700 text-pretty">
            نتیجه را با{" "}
            <code dir="ltr" className="rounded bg-stone-100 px-1.5 py-0.5">
              uv run villasanj er evaluate
            </code>{" "}
            ببینید.
          </p>
        </section>
      )}

      {status === "error" && (
        <button
          type="button"
          onClick={() => void load()}
          className={cn("self-start rounded-lg border border-stone-300 bg-white px-4 py-2", FOCUS)}
        >
          تلاش دوباره
        </button>
      )}

      {task && status !== "done" && (
        <>
          <p className="text-sm text-stone-600 text-pretty">{faDistance(task.distance)}</p>
          <div className={cn("grid gap-4 lg:grid-cols-2", status === "loading" && "opacity-60")}>
            <ListingColumn card={task.left} onOpen={openPhoto} />
            <ListingColumn card={task.right} onOpen={openPhoto} />
          </div>
        </>
      )}

      <nav
        aria-label="تصمیم درباره‌ی این جفت"
        className="fixed inset-x-0 bottom-0 z-10 border-t border-stone-200 bg-white/95 pb-[env(safe-area-inset-bottom)]"
      >
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-4 py-3">
          {LABELS.map((label) => (
            <button
              key={label}
              type="button"
              disabled={!task || saving || status !== "ready"}
              aria-pressed={task?.current_label === label}
              aria-keyshortcuts={KEY_HINT[label]}
              onClick={() => void save(label)}
              className={cn(
                "flex min-h-11 items-center gap-2 rounded-lg border px-4 py-2 font-medium disabled:opacity-50",
                task?.current_label === label
                  ? "border-stone-900 bg-stone-900 text-white"
                  : "border-stone-300 bg-white text-stone-900",
                FOCUS,
              )}
            >
              {LABEL_TEXT[label]}
              <kbd dir="ltr" className="rounded border border-current/30 px-1.5 text-xs">
                {KEY_HINT[label]}
              </kbd>
            </button>
          ))}
          <span className="ms-auto flex gap-2">
            <button
              type="button"
              disabled={!task || task.position === 0}
              aria-keyshortcuts="ArrowRight"
              onClick={() => move(-1)}
              className={cn(
                "min-h-11 rounded-lg border border-stone-300 bg-white px-3 disabled:opacity-50",
                FOCUS,
              )}
            >
              قبلی
            </button>
            <button
              type="button"
              disabled={!task || task.position >= task.total - 1}
              aria-keyshortcuts="ArrowLeft"
              onClick={() => move(1)}
              className={cn(
                "min-h-11 rounded-lg border border-stone-300 bg-white px-3 disabled:opacity-50",
                FOCUS,
              )}
            >
              بعدی
            </button>
          </span>
        </div>
      </nav>

      <dialog
        ref={dialog}
        aria-label="عکس بزرگ"
        onClose={() => setLightbox(null)}
        onKeyDown={(event) => {
          if (!lightbox || (event.code !== "ArrowLeft" && event.code !== "ArrowRight")) return;
          event.preventDefault(); // right to left: ArrowLeft shows the next photo
          const index = lightbox.index + (event.code === "ArrowLeft" ? 1 : -1);
          if (index >= 0 && index < lightbox.card.photos.length)
            setLightbox({ ...lightbox, index });
        }}
        className="m-auto max-h-dvh max-w-5xl overscroll-contain rounded-xl bg-stone-950 p-0 backdrop:bg-black/80"
      >
        {lightbox && (
          <div className="flex flex-col gap-2 p-3">
            <div className="flex items-center justify-between gap-2 text-sm text-stone-200">
              <span className="tabular-nums">
                {lightbox.card.platform_name} · عکس {faNumber(lightbox.index + 1)} از{" "}
                {faNumber(lightbox.card.photos.length)}
              </span>
              <span className="flex gap-2">
                <button
                  type="button"
                  disabled={lightbox.index === 0}
                  onClick={() => setLightbox({ ...lightbox, index: lightbox.index - 1 })}
                  className={cn("rounded px-3 py-1 text-white disabled:opacity-40", FOCUS)}
                >
                  قبلی
                </button>
                <button
                  type="button"
                  disabled={lightbox.index >= lightbox.card.photos.length - 1}
                  onClick={() => setLightbox({ ...lightbox, index: lightbox.index + 1 })}
                  className={cn("rounded px-3 py-1 text-white disabled:opacity-40", FOCUS)}
                >
                  بعدی
                </button>
                <button
                  type="button"
                  autoFocus
                  onClick={() => dialog.current?.close()}
                  className={cn("rounded px-3 py-1 text-white", FOCUS)}
                >
                  بستن
                </button>
              </span>
            </div>
            {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server */}
            <img
              src={lightbox.card.photos[lightbox.index]}
              alt={`عکس ${faNumber(lightbox.index + 1)} آگهی ${lightbox.card.platform_name}`}
              referrerPolicy="no-referrer"
              className="max-h-[80dvh] w-auto object-contain"
            />
          </div>
        )}
      </dialog>
    </main>
  );
}

function Fact({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-stone-100 py-1">
      <dt className="text-stone-600">{term}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function ListingColumn({
  card,
  onOpen,
}: {
  card: ListingCard;
  onOpen: (card: ListingCard, index: number) => void;
}) {
  const headingId = `listing-${card.id.replace(/[^a-zA-Z0-9]/g, "-")}`;
  const place = [card.city, card.locality].filter(Boolean).join("، ") || "نامشخص";
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-xl border border-stone-200 bg-white p-4"
    >
      <div className="flex flex-col gap-1">
        <p className="text-xs font-medium text-emerald-800">{card.platform_name}</p>
        <h2 id={headingId} className="text-lg font-semibold text-balance">
          <a
            href={card.url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn("underline-offset-4 hover:underline", FOCUS)}
          >
            {card.title}
          </a>
        </h2>
      </div>
      <dl className="grid gap-x-6 text-sm sm:grid-cols-2">
        <Fact term="محل" value={place} />
        <Fact term="نوع" value={faPropertyType(card.property_type)} />
        <Fact term="اتاق خواب" value={faNumber(card.bedrooms)} />
        <Fact term="سرویس بهداشتی" value={faNumber(card.bathrooms)} />
        <Fact term="متراژ" value={faNumber(card.area_m2, " متر")} />
        <Fact
          term="ظرفیت (پایه / حداکثر)"
          value={`${faNumber(card.base_capacity)} / ${faNumber(card.max_capacity)}`}
        />
        <Fact term="قیمت پایه هر شب" value={faNumber(card.base_price_toman, " تومان")} />
        <Fact
          term="امتیاز"
          value={
            card.rating === null
              ? "بدون امتیاز"
              : `${faNumber(card.rating)} از ${faNumber(card.rating_count)} نظر`
          }
        />
      </dl>
      {card.description && (
        <details className="text-sm">
          <summary className={cn("cursor-pointer text-stone-700", FOCUS)}>توضیحات آگهی</summary>
          <p className="mt-2 leading-7 whitespace-pre-line text-stone-700 text-pretty">
            {card.description}
          </p>
        </details>
      )}
      {card.photos.length === 0 ? (
        <p className="text-sm text-stone-600">این آگهی عکسی منتشر نکرده است.</p>
      ) : (
        <ul className="grid grid-cols-3 gap-2" aria-label={`عکس‌های ${card.platform_name}`}>
          {card.photos.map((url, index) => (
            <li key={url}>
              <button
                type="button"
                onClick={() => onOpen(card, index)}
                aria-label={`بزرگ‌نمایی عکس ${faNumber(index + 1)} از ${card.platform_name}`}
                className={cn("block w-full overflow-hidden rounded-md bg-stone-100", FOCUS)}
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server */}
                <img
                  src={url}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  referrerPolicy="no-referrer"
                  className="aspect-[4/3] w-full object-cover"
                />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
