import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { apiClient, type Review } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { apiBaseUrl } from "@/lib/health";
import { faNumber, faStayed } from "@/lib/listing";
import { fetchSummaryReviewTask } from "@/lib/summary-reviews";

import {
  ReviewSummarySection,
  ReviewSummarySkeleton,
  reviewAnchor,
} from "@/components/listing/reviews";
import { VerdictForm } from "./verdict-form";

export const metadata: Metadata = {
  title: "بازبینی خلاصه‌ی نظرها · ویلاسنج",
  robots: { index: false, follow: false },
};

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";
const MAX_REVIEWS = 60; // the summary reads the 40 most recent with text: all of them are here

type SearchParams = Record<string, string | string[] | undefined>;

export default async function SummaryReviewPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const queue = typeof params.queue === "string" ? params.queue : "summaries-v1";
  const labeler = typeof params.labeler === "string" ? params.labeler : "owner";
  const raw = typeof params.position === "string" ? Number.parseInt(params.position, 10) : NaN;
  const first = await fetchSummaryReviewTask(
    apiBaseUrl(),
    queue,
    labeler,
    Number.isNaN(raw) ? undefined : raw,
  );
  if (first.kind !== "ready") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-semibold text-balance">بازبینی خلاصه‌ی نظرها</h1>
        <p className="mt-3 text-stone-600" role="alert">
          {first.kind === "missing"
            ? `صف «${queue}» هنوز ساخته نشده است.`
            : "بارگذاری ممکن نشد. API در دسترس است؟"}
        </p>
      </main>
    );
  }
  const task = first.task;
  const path = { platform: task.platform, external_id: task.external_id };
  const api = apiClient();
  const [listing, reviews] = await Promise.all([
    api.GET("/listings/{platform}/{external_id}", { params: { path }, cache: "no-store" }),
    api.GET("/listings/{platform}/{external_id}/reviews", { params: { path }, cache: "no-store" }),
  ]);
  const shown: Review[] = (reviews.data ?? []).slice(0, MAX_REVIEWS);
  const order = Object.fromEntries(shown.map((r, index) => [r.id, index + 1]));
  return (
    <main className="mx-auto max-w-3xl px-4 pt-6 pb-16">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold text-balance">بازبینی خلاصه‌ی نظرها</h1>
        <p className="text-sm text-stone-600 tabular-nums">
          آگهی {faNumber(task.position)} از {faNumber(task.total)} · {faNumber(task.reviewed)}{" "}
          بازبینی‌شده
        </p>
      </header>
      <p className="mt-2 text-sm text-pretty text-stone-600">
        خلاصه را با نظرهای زیر مقایسه کنید: آیا هر نکته در نظرها آمده و چیزی مهم جا نیفتاده؟ هدف:
        دست‌کم ۱۸ از ۲۰ وفادار (نتیجه در هر حال ثبت می‌شود).
      </p>
      <h2 className="mt-5 font-medium text-balance">
        <Link
          href={`/listings/${task.platform}/${task.external_id}`}
          className={cn("underline underline-offset-4", FOCUS)}
          target="_blank"
        >
          {listing.data?.title ?? `${task.platform}/${task.external_id}`}
        </Link>
      </h2>
      <Suspense fallback={<ReviewSummarySkeleton />}>
        <ReviewSummarySection platform={task.platform} id={task.external_id} order={order} />
      </Suspense>
      <VerdictForm
        key={`${task.platform}/${task.external_id}`}
        queue={queue}
        labeler={labeler}
        task={task}
      />
      <section aria-labelledby="raw-title" className="mt-8">
        <h2 id="raw-title" className="font-medium">
          نظرهای خام ({faNumber(shown.length)})
        </h2>
        <ol className="mt-3 divide-y divide-stone-200 rounded-lg border border-stone-200 bg-white">
          {shown.map((review, index) => (
            <li key={review.id} id={reviewAnchor(review.id)} className="scroll-mt-4 p-3 text-sm">
              <p className="text-xs text-stone-600 tabular-nums">
                نظر {faNumber(index + 1)} ·{" "}
                {review.rating === null ? "بدون امتیاز" : `${faNumber(review.rating)} از ۵`} ·{" "}
                {faStayed(review)}
              </p>
              <p className="mt-1 text-pretty">{review.text ?? "بدون متن"}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
