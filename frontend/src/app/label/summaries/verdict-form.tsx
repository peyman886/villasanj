"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { type SummaryReviewTask, verdictFor } from "@/lib/summary-reviews";

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";
const BUTTON = cn(
  "rounded-lg border px-4 py-2 text-sm font-medium disabled:opacity-50",
  "border-stone-300 bg-white hover:bg-stone-50",
  FOCUS,
);

/** Faithful or not (keys Y and N), an optional note, and moving through the queue. */
export function VerdictForm({
  queue,
  labeler,
  task,
}: {
  queue: string;
  labeler: string;
  task: SummaryReviewTask;
}) {
  const router = useRouter();
  const [note, setNote] = useState(task.note ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const go = useCallback(
    (position: number) => {
      const params = new URLSearchParams({ queue, labeler, position: String(position) });
      router.push(`/label/summaries?${params}`);
    },
    [router, queue, labeler],
  );

  const save = useCallback(
    async (faithful: boolean) => {
      setSaving(true);
      setMessage("");
      try {
        const response = await fetch("/api/summary-review", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            queue,
            labeler,
            platform: task.platform,
            external_id: task.external_id,
            faithful,
            note: note.trim() || null,
          }),
        });
        if (!response.ok) throw new Error(String(response.status));
        if (task.position < task.total) go(task.position + 1);
        else {
          setMessage("ثبت شد. این آخرین آگهی صف بود.");
          router.refresh();
        }
      } catch {
        setMessage("ثبت نشد. دوباره امتحان کنید.");
      } finally {
        setSaving(false);
      }
    },
    [queue, labeler, task, note, go, router],
  );

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest("textarea, input") || saving) return;
      const verdict = verdictFor(event);
      if (verdict !== null) {
        event.preventDefault();
        void save(verdict);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save, saving]);

  const current = task.faithful === null ? null : task.faithful ? "وفادار است" : "وفادار نیست";
  return (
    <section
      aria-labelledby="verdict-title"
      className="mt-6 rounded-lg border border-stone-200 p-4"
    >
      <h2 id="verdict-title" className="font-medium">
        این خلاصه به نظرها وفادار است؟
      </h2>
      {current ? <p className="mt-1 text-sm text-stone-600">رأی قبلی شما: {current}</p> : null}
      <label className="mt-3 block text-sm text-stone-700" htmlFor="verdict-note">
        یادداشت (اختیاری): کدام نکته در نظرها نیست یا چه چیز مهمی جا افتاده
      </label>
      <textarea
        id="verdict-note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        rows={2}
        maxLength={500}
        className={cn("mt-1 w-full rounded-lg border border-stone-300 p-2 text-sm", FOCUS)}
      />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" className={BUTTON} disabled={saving} onClick={() => save(true)}>
          وفادار است <kbd className="ms-1 text-xs text-stone-500">Y</kbd>
        </button>
        <button type="button" className={BUTTON} disabled={saving} onClick={() => save(false)}>
          وفادار نیست <kbd className="ms-1 text-xs text-stone-500">N</kbd>
        </button>
        <span className="flex-1" />
        <button
          type="button"
          className={BUTTON}
          disabled={task.position <= 1}
          onClick={() => go(task.position - 1)}
        >
          قبلی
        </button>
        <button
          type="button"
          className={BUTTON}
          disabled={task.position >= task.total}
          onClick={() => go(task.position + 1)}
        >
          بعدی
        </button>
      </div>
      <p role="status" className="mt-2 min-h-5 text-sm text-stone-700">
        {message}
      </p>
    </section>
  );
}
