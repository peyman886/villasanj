import { ArrowUpLeft, CircleCheck, ClipboardList } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ProgressBar } from "@/components/charts/bars";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { faInt } from "@/lib/format";
import { apiBaseUrl } from "@/lib/health";
import { QUEUES, fetchReviewProgress } from "@/lib/reviews";

export const metadata: Metadata = {
  title: "بازبینی‌های مالک",
  description: "صف‌های بازبینی انسانی ویلاسنج و پیشرفت هر کدام.",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

export default async function ReviewHub() {
  const progress = await fetchReviewProgress(apiBaseUrl());
  const byQueue = new Map(progress.kind === "ready" ? progress.value.map((p) => [p.queue, p]) : []);
  const open = QUEUES.filter((q) => q.open);
  const finished = QUEUES.filter((q) => !q.open);
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <p className="text-sm font-semibold text-accent">ابزار داخلی</p>
      <h1 className="mt-2 text-3xl font-bold text-balance">بازبینی‌های مالک</h1>
      <p className="mt-3 max-w-3xl text-pretty text-fg-muted">
        هر سنجه‌ی کیفیت ویلاسنج روی برچسب انسان است، نه مدل زبانی. این صفحه همه‌ی صف‌های بازبینی و
        پیشرفت هر کدام را نشان می‌دهد. برچسب‌ها با نام «owner» ذخیره می‌شوند و هر وقت لازم شد می‌شود
        عوضشان کرد؛ آخرین رأی ملاک است.
      </p>
      {progress.kind !== "ready" ? (
        <Callout kind="caution" title="پیشرفت صف‌ها خوانده نشد" className="mt-6">
          API در دسترس نیست؛ پیوندها کار می‌کنند ولی شمارش‌ها نه.
        </Callout>
      ) : null}
      <h2 className="mt-10 flex items-center gap-2 text-xl font-semibold">
        <ClipboardList aria-hidden="true" className="size-5 text-fg-muted" />
        باقی‌مانده
      </h2>
      <ul className="mt-4 grid gap-4 md:grid-cols-3">
        {open.map((q) => {
          const p = byQueue.get(q.queue);
          const done = p ? p.done >= p.total && p.total > 0 : false;
          return (
            <li
              key={q.queue}
              className="flex flex-col rounded-card border border-line bg-surface p-5 shadow-raised"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="ltr font-mono text-xs text-accent">{q.queue}</span>
                {done ? <Badge tone="verified">کامل</Badge> : <Badge tone="info">باز</Badge>}
              </div>
              <h3 className="mt-2 font-semibold text-balance">{q.title}</h3>
              <p className="mt-2 text-sm leading-7 text-pretty text-fg-muted">{q.description}</p>
              <div className="mt-auto space-y-3 pt-4">
                {p ? (
                  <ProgressBar
                    label={`${q.unit}ها`}
                    value={p.done}
                    max={Math.max(1, p.total)}
                    display={`${faInt(p.done)} از ${faInt(p.total)}`}
                  />
                ) : null}
                <Link
                  href={q.href}
                  className="focus-ring inline-flex items-center gap-1 rounded-sm font-medium text-accent hover:underline"
                >
                  {p && p.done > 0 ? "ادامه" : "شروع"}
                  <ArrowUpLeft aria-hidden="true" className="size-4" />
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
      <h2 className="mt-12 flex items-center gap-2 text-xl font-semibold">
        <CircleCheck aria-hidden="true" className="size-5 text-fg-muted" />
        انجام‌شده
      </h2>
      <ul className="mt-4 divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        {finished.map((q) => {
          const p = byQueue.get(q.queue);
          return (
            <li key={q.queue} className="flex flex-wrap items-center gap-x-4 gap-y-1 p-4">
              <Link
                href={q.href}
                className="focus-ring rounded-sm font-medium hover:text-accent hover:underline"
              >
                {q.title}
              </Link>
              <span className="ltr font-mono text-xs text-fg-subtle">{q.queue}</span>
              <span className="text-sm text-pretty text-fg-muted">{q.description}</span>
              {p ? (
                <span className="ms-auto text-sm text-fg-muted tabular-nums">
                  {faInt(p.done)} از {faInt(p.total)} {q.unit}
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
