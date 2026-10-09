import type { Metadata } from "next";

import { ReviewShell, ReviewUnavailable } from "@/components/review/shell";
import { Badge } from "@/components/ui/badge";
import { apiBaseUrl } from "@/lib/health";
import { faDay, faNumber } from "@/lib/listing";
import { fetchRelevanceTask, intentRows } from "@/lib/reviews";

import { RelevanceGrader } from "./relevance-grader";

export const metadata: Metadata = {
  title: "داوری مرتبط‌بودن نتیجه‌ها",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;
const TITLE = "داوری مرتبط‌بودن نتیجه‌های جستجو";

export default async function RelevancePage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const queue = typeof params.queue === "string" ? params.queue : "relevance-v1";
  const labeler = typeof params.labeler === "string" ? params.labeler : "owner";
  const raw = typeof params.position === "string" ? Number.parseInt(params.position, 10) : NaN;
  const fetched = await fetchRelevanceTask(
    apiBaseUrl(),
    queue,
    labeler,
    Number.isNaN(raw) ? undefined : raw,
  );
  if (fetched.kind !== "ready") {
    return <ReviewUnavailable title={TITLE} missing={fetched.kind === "missing"} queue={queue} />;
  }
  const task = fetched.value;
  return (
    <ReviewShell title={TITLE} done={task.queries_done} total={task.total} unit="پرسش">
      <p className="max-w-3xl text-sm text-pretty text-fg-muted">
        هر ویلا را با پرسش بسنجید: اگر کاربری با این پرسش آن را ببیند، همان چیزی است که می‌خواست؟
        ترتیب کارت‌ها تصادفی است و نمی‌گوید کدام رتبه‌بندی آن را آورده. همه‌ی ویلاها برای همین تاریخ
        و همین تعداد نفر آزاد دیده شده‌اند. کلیدها: ۲ مرتبط، ۱ تا حدی، ۰ نامرتبط؛ بعد از هر رأی،
        کارت بعدی انتخاب می‌شود.
      </p>
      <section
        aria-labelledby="query-title"
        className="mt-6 rounded-card border border-line bg-surface p-5 shadow-raised"
      >
        <p className="text-sm text-fg-muted tabular-nums">
          پرسش {faNumber(task.position)} از {faNumber(task.total)} · {faDay(task.check_in)} تا{" "}
          {faDay(task.check_out)}
          {task.guests ? ` · ${faNumber(task.guests)} نفر` : ""}
        </p>
        <h2 id="query-title" className="mt-2 text-2xl leading-10 font-semibold text-balance">
          «{task.query}»
        </h2>
        <ul aria-label="برداشت جستجو" className="mt-3 flex flex-wrap gap-2">
          {intentRows(task.intent).map(([label, value]) => (
            <li key={label}>
              <Badge tone="brand">
                {label}: {value}
              </Badge>
            </li>
          ))}
        </ul>
      </section>
      <RelevanceGrader
        key={`${queue}-${task.position}`}
        queue={queue}
        labeler={labeler}
        task={task}
      />
    </ReviewShell>
  );
}
