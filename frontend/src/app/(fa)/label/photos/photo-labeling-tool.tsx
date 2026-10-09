"use client";

import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { faNumber } from "@/lib/listing";
import {
  type PhotoTag,
  type PhotoTask,
  type PhotoTaskResult,
  photoShortcutFor,
  toggled,
} from "@/lib/photo-labels";

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

export function PhotoLabelingTool({
  queue,
  labeler,
  first,
}: {
  queue: string;
  labeler: string;
  first: PhotoTaskResult;
}) {
  const [task, setTask] = useState<PhotoTask | null>(first.kind === "ready" ? first.task : null);
  const [present, setPresent] = useState<PhotoTag[]>(
    first.kind === "ready" ? first.task.present : [],
  );
  const [message, setMessage] = useState(
    first.kind === "missing"
      ? `صف «${queue}» هنوز ساخته نشده است.`
      : first.kind === "error"
        ? "بارگذاری عکس ممکن نشد. API در دسترس است؟"
        : "",
  );
  const [saving, setSaving] = useState(false);

  const load = useCallback(
    async (position?: number) => {
      const params = new URLSearchParams({ queue, labeler });
      if (position !== undefined) params.set("position", String(position));
      try {
        const response = await fetch(`/api/photo-label/task?${params}`, { cache: "no-store" });
        const result = (await response.json()) as PhotoTaskResult;
        if (result.kind === "ready") {
          setTask(result.task);
          setPresent(result.task.present);
          setMessage("");
          window.scrollTo({ top: 0 });
        } else {
          setMessage("بارگذاری عکس ممکن نشد.");
        }
      } catch {
        setMessage("بارگذاری عکس ممکن نشد.");
      }
    },
    [queue, labeler],
  );

  const save = useCallback(async () => {
    if (!task || saving) return;
    setSaving(true);
    try {
      const response = await fetch("/api/photo-label", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ queue, sha256: task.sha256, present, labeler }),
      });
      if (response.status !== 204) throw new Error(String(response.status));
      await load(task.position < task.total ? task.position + 1 : undefined);
    } catch {
      setMessage("ذخیره نشد؛ دوباره امتحان کنید.");
    } finally {
      setSaving(false);
    }
  }, [task, saving, queue, present, labeler, load]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!task) return;
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA"].includes(target.tagName)) return;
      const shortcut = photoShortcutFor(event);
      if (!shortcut) return;
      event.preventDefault();
      if (shortcut.kind === "toggle") {
        const tag = task.tags[shortcut.index];
        if (tag) setPresent((current) => toggled(current, tag.code));
      } else if (shortcut.kind === "save") {
        void save();
      } else if (shortcut.kind === "next" && task.position < task.total) {
        void load(task.position + 1);
      } else if (shortcut.kind === "previous" && task.position > 1) {
        void load(task.position - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [task, save, load]);

  if (!task) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-xl font-semibold">برچسب عکس‌ها</h1>
        <p className="mt-3 text-stone-600" role="alert">
          {message}
        </p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 pt-5 pb-28">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold text-balance">در این عکس چه دیده می‌شود؟</h1>
        <p className="text-sm text-stone-600 tabular-nums" aria-live="polite">
          عکس {faNumber(task.position)} از {faNumber(task.total)} · برچسب‌خورده{" "}
          {faNumber(task.labelled)}
          {task.done ? " · همه برچسب خورده‌اند" : ""}
        </p>
      </header>
      <p className="mt-1 text-sm text-pretty text-stone-600">
        هر چیزی را که واقعاً در عکس دیده می‌شود انتخاب کنید (کلیدهای ۱ تا ۶)، بعد ثبت (Enter). اگر
        هیچ‌کدام نیست، فقط ثبت کنید.
      </p>
      {message ? (
        <p className="mt-3 text-sm text-red-800" role="alert">
          {message}
        </p>
      ) : null}
      {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server */}
      <img
        key={task.sha256}
        src={task.url}
        alt={`عکس ${faNumber(task.position)} صف برچسب‌گذاری`}
        referrerPolicy="no-referrer"
        className="mt-4 max-h-[60dvh] w-full rounded-lg bg-stone-200 object-contain"
      />
      <fieldset className="mt-4">
        <legend className="sr-only">برچسب‌های این عکس</legend>
        <div className="flex flex-wrap gap-2">
          {task.tags.map((tag, index) => {
            const on = present.includes(tag.code);
            return (
              <button
                key={tag.code}
                type="button"
                aria-pressed={on}
                onClick={() => setPresent((current) => toggled(current, tag.code))}
                className={cn(
                  "rounded-full border px-4 py-2 text-sm",
                  on
                    ? "border-emerald-800 bg-emerald-800 text-white"
                    : "border-stone-300 bg-white text-stone-800 hover:bg-stone-100",
                  FOCUS,
                )}
              >
                <span className="me-2 rounded bg-black/10 px-1.5 text-xs tabular-nums">
                  {faNumber(index + 1)}
                </span>
                {tag.name}
              </button>
            );
          })}
        </div>
      </fieldset>
      <nav
        aria-label="ثبت و جابه‌جایی"
        className="fixed inset-x-0 bottom-0 border-t border-stone-200 bg-white/95 px-4 py-3"
        style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
      >
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={saving}
            className={cn(
              "rounded-lg bg-emerald-800 px-5 py-2 font-medium text-white hover:bg-emerald-900 disabled:opacity-60",
              FOCUS,
            )}
          >
            ثبت و بعدی (Enter)
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => void load(task.position - 1)}
              disabled={task.position <= 1}
              className={cn(
                "rounded-lg border border-stone-300 px-4 py-2 disabled:opacity-50",
                FOCUS,
              )}
            >
              قبلی
            </button>
            <button
              type="button"
              onClick={() => void load(task.position + 1)}
              disabled={task.position >= task.total}
              className={cn(
                "rounded-lg border border-stone-300 px-4 py-2 disabled:opacity-50",
                FOCUS,
              )}
            >
              بعدی
            </button>
          </div>
        </div>
      </nav>
    </main>
  );
}
