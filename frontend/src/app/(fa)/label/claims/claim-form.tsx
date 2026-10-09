"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  type ClaimTask,
  completeStances,
  STANCE_TEXT,
  STANCES,
  type Stance,
} from "@/lib/claim-labels";
import { cn } from "@/lib/cn";
import { FEATURE_TEXT } from "@/lib/search";

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";
const BUTTON = cn(
  "rounded-lg border px-4 py-2 text-sm font-medium disabled:opacity-50",
  "border-stone-300 bg-white hover:bg-stone-50",
  FOCUS,
);

/** One stance per feature (native radio groups: arrow keys move within a group). */
export function ClaimForm({
  queue,
  labeler,
  task,
}: {
  queue: string;
  labeler: string;
  task: ClaimTask;
}) {
  const router = useRouter();
  const [stances, setStances] = useState<Record<string, Stance>>(() =>
    completeStances(task.features, task.current as Record<string, Stance | undefined>),
  );
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  function go(position: number) {
    const params = new URLSearchParams({ queue, labeler, position: String(position) });
    router.push(`/label/claims?${params}`);
  }

  async function save() {
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch("/api/claim-label", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          queue,
          labeler,
          platform: task.platform,
          external_id: task.external_id,
          stances,
        }),
      });
      if (!response.ok) throw new Error(String(response.status));
      if (task.position < task.total) go(task.position + 1);
      else {
        setMessage("ثبت شد. این آخرین توضیح صف بود.");
        router.refresh();
      }
    } catch {
      setMessage("ثبت نشد. دوباره امتحان کنید.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="mt-6 rounded-lg border border-stone-200 p-4"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      <p className="font-medium">این متن درباره‌ی هر امکان چه می‌گوید؟</p>
      <div className="mt-3 space-y-3">
        {task.features.map((feature) => (
          <fieldset key={feature} className="flex flex-wrap items-center gap-x-4 gap-y-1">
            <legend className="w-28 shrink-0 text-sm font-medium">
              {FEATURE_TEXT[feature] ?? feature}
            </legend>
            {STANCES.map((stance) => (
              <label key={stance} className="flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  name={feature}
                  value={stance}
                  checked={stances[feature] === stance}
                  onChange={() => setStances((s) => ({ ...s, [feature]: stance }))}
                  className={FOCUS}
                />
                {STANCE_TEXT[stance]}
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="submit" className={BUTTON} disabled={saving}>
          ثبت و بعدی <kbd className="ms-1 text-xs text-stone-500">Enter</kbd>
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
    </form>
  );
}
