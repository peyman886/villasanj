"use client";

import { Check, PenLine, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { type QueryReviewTask, queryVerdictFor } from "@/lib/reviews";

const FIELDS =
  "dates {kind, which, weekday, month, day, year} · nights · guest_parts · party · bedrooms_min · budget {max_toman, basis} · max_drive {value, unit} · places · features · unhandled";

/** Correct (Y) saves and moves on; needs a fix (N) opens the corrected intent and a note. */
export function QueryReviewForm({
  queue,
  labeler,
  task,
}: {
  queue: string;
  labeler: string;
  task: QueryReviewTask;
}) {
  const router = useRouter();
  const [fixing, setFixing] = useState(task.correct === false);
  const [json, setJson] = useState(JSON.stringify(task.corrected ?? task.expected, null, 2));
  const [note, setNote] = useState(task.reviewer_note ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const go = useCallback(
    (position: number) => {
      const params = new URLSearchParams({ queue, labeler, position: String(position) });
      router.push(`/label/queries?${params}`);
    },
    [router, queue, labeler],
  );

  const save = useCallback(
    async (correct: boolean, corrected: Record<string, unknown> | null) => {
      setSaving(true);
      setMessage("");
      try {
        const response = await fetch("/api/query-review", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            queue,
            labeler,
            position: task.position,
            correct,
            corrected,
            note: note.trim() || null,
          }),
        });
        if (response.status === 422) {
          const body = (await response.json()) as { detail?: string };
          setMessage(`برداشت اصلاح‌شده معتبر نیست: ${body.detail ?? ""}`);
          return;
        }
        if (!response.ok) throw new Error(String(response.status));
        if (task.position < task.total) go(task.position + 1);
        else {
          setMessage("ثبت شد. این آخرین پرسش بود.");
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

  const saveCorrection = useCallback(() => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(json);
    } catch {
      setMessage("متن برداشت JSON معتبر نیست.");
      return;
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      setMessage("برداشت باید یک شیء JSON باشد.");
      return;
    }
    void save(false, parsed as Record<string, unknown>);
  }, [json, save]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.closest("textarea, input") || saving) return;
      const verdict = queryVerdictFor(event);
      if (verdict === true) {
        event.preventDefault();
        void save(true, null);
      } else if (verdict === false) {
        event.preventDefault();
        setFixing(true);
      }
    }
    window.addEventListener("keydown", onKey);
    document.documentElement.dataset.reviewKeys = "on"; // the keyboard works from here on
    return () => {
      window.removeEventListener("keydown", onKey);
      delete document.documentElement.dataset.reviewKeys;
    };
  }, [save, saving]);

  return (
    <section aria-labelledby="verdict-title" className="mt-6 space-y-4">
      <h2 id="verdict-title" className="sr-only">
        رأی شما
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={saving} onClick={() => save(true, null)}>
          <Check aria-hidden="true" className="size-4" />
          درست است <kbd className="text-xs opacity-80">Y</kbd>
        </Button>
        <Button variant="secondary" disabled={saving} onClick={() => setFixing(true)}>
          <PenLine aria-hidden="true" className="size-4" />
          اصلاح لازم دارد <kbd className="text-xs text-fg-muted">N</kbd>
        </Button>
        <span className="flex-1" />
        <Button variant="ghost" disabled={task.position <= 1} onClick={() => go(task.position - 1)}>
          قبلی
        </Button>
        <Button
          variant="ghost"
          disabled={task.position >= task.total}
          onClick={() => go(task.position + 1)}
        >
          بعدی
        </Button>
      </div>
      {fixing ? (
        <div className="space-y-3 rounded-card border border-line bg-surface p-4">
          <label htmlFor="corrected" className="block text-sm font-medium">
            برداشت درست (JSON)
          </label>
          <p className="ltr text-xs text-fg-muted">{FIELDS}</p>
          <textarea
            id="corrected"
            dir="ltr"
            spellCheck={false}
            value={json}
            onChange={(event) => setJson(event.target.value)}
            rows={10}
            className="focus-ring w-full rounded-control border border-line-strong bg-sunken p-3 font-mono text-sm"
          />
          <label htmlFor="note" className="block text-sm font-medium">
            یادداشت (اختیاری): چه چیزی اشتباه بود
          </label>
          <textarea
            id="note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            maxLength={1000}
            className="focus-ring w-full rounded-control border border-line-strong bg-surface p-3 text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <Button disabled={saving} onClick={saveCorrection}>
              <PenLine aria-hidden="true" className="size-4" />
              ثبت با این اصلاح
            </Button>
            <Button variant="secondary" disabled={saving} onClick={() => save(false, null)}>
              <X aria-hidden="true" className="size-4" />
              کنار گذاشته شود (بدون اصلاح)
            </Button>
          </div>
        </div>
      ) : null}
      <p role="status" className="min-h-5 text-sm text-fg">
        {message}
      </p>
    </section>
  );
}
