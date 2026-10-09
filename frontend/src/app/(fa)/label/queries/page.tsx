import type { Metadata } from "next";

import { ReviewShell, ReviewUnavailable } from "@/components/review/shell";
import { Badge } from "@/components/ui/badge";
import { apiBaseUrl } from "@/lib/health";
import { faNumber } from "@/lib/listing";
import { fetchQueryReviewTask, intentRows } from "@/lib/reviews";

import { QueryReviewForm } from "./query-review-form";

export const metadata: Metadata = {
  title: "بازبینی مجموعه‌ی پرسش‌ها",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;
const TITLE = "بازبینی مجموعه‌ی پرسش‌های جستجو";

export default async function QueryReviewPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const queue = typeof params.queue === "string" ? params.queue : "queries-v1";
  const labeler = typeof params.labeler === "string" ? params.labeler : "owner";
  const raw = typeof params.position === "string" ? Number.parseInt(params.position, 10) : NaN;
  const fetched = await fetchQueryReviewTask(
    apiBaseUrl(),
    queue,
    labeler,
    Number.isNaN(raw) ? undefined : raw,
  );
  if (fetched.kind !== "ready") {
    return <ReviewUnavailable title={TITLE} missing={fetched.kind === "missing"} queue={queue} />;
  }
  const task = fetched.value;
  const rows = intentRows(task.expected);
  const previous =
    task.correct === null
      ? null
      : task.correct
        ? "درست است"
        : task.corrected
          ? "اصلاح شد"
          : "کنار گذاشته شد";
  return (
    <ReviewShell title={TITLE} done={task.reviewed} total={task.total} unit="پرسش">
      <p className="max-w-3xl text-sm text-pretty text-fg-muted">
        هر پرسش را بخوانید و ببینید برداشت نوشته‌شده همان چیزی است که یک آدم از آن می‌فهمد یا نه.
        فقط چیزی که در خود پرسش آمده باید در برداشت باشد؛ هیچ عددی که گفته نشده نباید اضافه شود.
        وقتی همه‌ی ۵۰ پرسش بازبینی شد، ارزیابی روی همین مجموعه دوباره اجرا می‌شود.
      </p>
      <section
        aria-labelledby="case-title"
        className="mt-6 rounded-card border border-line bg-surface p-5 shadow-raised"
      >
        <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
          <span className="tabular-nums">
            پرسش {faNumber(task.position)} از {faNumber(task.total)}
          </span>
          {previous ? <Badge tone="muted">رأی قبلی شما: {previous}</Badge> : null}
        </div>
        <h2 id="case-title" className="mt-3 text-2xl leading-10 font-semibold text-balance">
          «{task.query}»
        </h2>
        <h3 className="mt-6 text-sm font-semibold text-fg">برداشت مورد انتظار</h3>
        {rows.length ? (
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            {rows.map(([label, value]) => (
              <div key={label} className="rounded-control border border-line bg-sunken px-3 py-2">
                <dt className="text-xs text-fg-muted">{label}</dt>
                <dd className="mt-0.5 font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="mt-2 rounded-control border border-line bg-sunken px-3 py-2 text-sm">
            هیچ شرطی: این پرسش چیزی برای جستجو نمی‌گوید.
          </p>
        )}
        {task.note ? (
          <p className="mt-4 text-sm text-pretty text-fg-muted">
            <span className="font-medium text-fg">یادداشت پیش‌نویس:</span>{" "}
            <span dir="auto" className="block text-start">
              {task.note}
            </span>
          </p>
        ) : null}
      </section>
      <QueryReviewForm
        key={`${queue}-${task.position}`}
        queue={queue}
        labeler={labeler}
        task={task}
      />
    </ReviewShell>
  );
}
