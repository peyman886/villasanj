import { MessageSquareReply, Quote, Sparkles, Star, ThumbsDown, ThumbsUp } from "lucide-react";
import type { ReactNode } from "react";

import { Sourced } from "@/components/sourced";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { Section } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/states";
import { apiClient, type Listing, type Review } from "@/lib/api/client";
import { faNumber, faStayed } from "@/lib/listing";
import { faDigits } from "@/lib/numbers";

const MAX_REVIEWS = 20;

export const reviewAnchor = (id: string) => `review-${id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;

export function Stars({ rating }: { rating: number }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-hidden="true">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={
            n <= Math.round(rating)
              ? "size-3.5 fill-amber-400 text-amber-500"
              : "size-3.5 text-sand-300"
          }
        />
      ))}
    </span>
  );
}

/** One guest review; the author's name is never stored. */
export function ReviewItem({
  review,
  index,
  idPrefix = "",
  badge,
  sourceName,
  now,
}: {
  review: Review;
  index: number;
  idPrefix?: string;
  badge?: ReactNode;
  sourceName: string;
  now: Date;
}) {
  return (
    <li id={reviewAnchor(`${idPrefix}${review.id}`)} className="scroll-mt-24 p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <span className="text-xs text-fg-subtle tabular-nums">نظر {faNumber(index + 1)}</span>
        {badge}
        {review.rating === null ? (
          <span className="text-fg-subtle">بدون امتیاز</span>
        ) : (
          <span className="flex items-center gap-1.5 font-medium tabular-nums">
            <Stars rating={review.rating} />
            <Sourced
              id={`${idPrefix}review-${index}`}
              label="امتیاز این نظر"
              provenance={review.provenance}
              sourceName={sourceName}
              now={now}
            >
              {faNumber(review.rating)} از ۵
            </Sourced>
          </span>
        )}
        <span className="text-fg-muted">{faStayed(review)}</span>
        {review.host_replied ? (
          <span className="flex items-center gap-1 text-xs text-fg-subtle">
            <MessageSquareReply aria-hidden="true" className="size-3.5" />
            میزبان پاسخ داده
          </span>
        ) : null}
      </div>
      {review.text ? (
        <p className="mt-2 text-pretty">{faDigits(review.text)}</p>
      ) : (
        <p className="mt-2 text-sm text-fg-subtle">بدون متن</p>
      )}
    </li>
  );
}

export function ReviewsSection({
  listing,
  reviews,
  now,
  summary,
}: {
  listing: Listing;
  reviews: Review[];
  now: Date;
  summary?: ReactNode;
}) {
  const shown = reviews.slice(0, MAX_REVIEWS);
  return (
    <Section
      id="reviews"
      title="نظرهای مهمان‌ها"
      description={`نظرهایی که صفحه‌ی آگهی در ${listing.platform_name} نشان می‌داد (${faNumber(reviews.length)} نظر)؛ نام نویسنده‌ها ذخیره نمی‌شود.`}
    >
      {summary}
      {shown.length === 0 ? (
        <p className="text-sm text-fg-muted">نظری ذخیره نشده است.</p>
      ) : (
        <ol className="mt-4 divide-y divide-line rounded-card border border-line bg-surface">
          {shown.map((review, index) => (
            <ReviewItem
              key={review.id}
              review={review}
              index={index}
              sourceName={listing.platform_name}
              now={now}
            />
          ))}
        </ol>
      )}
      {reviews.length > shown.length ? (
        <p className="mt-2 text-sm text-fg-muted">
          و {faNumber(reviews.length - shown.length)} نظر دیگر در صفحه‌ی آگهی.
        </p>
      ) : null}
    </Section>
  );
}

type SummaryPoint = { text: string; review_ids: string[]; single_opinion: boolean };
export type Summary = { pros: SummaryPoint[]; cons: SummaryPoint[]; reviews_given: number };

function SummaryList({
  title,
  icon,
  points,
  order,
}: {
  title: string;
  icon: ReactNode;
  points: SummaryPoint[];
  order: Record<string, number>; // review id -> its number in the list below
}) {
  if (points.length === 0) return null;
  return (
    <div>
      <h3 className="flex items-center gap-1.5 text-sm font-semibold">
        {icon}
        {title}
      </h3>
      <ul className="mt-2 space-y-2 text-sm">
        {points.map((point) => (
          <li key={point.text} className="text-pretty">
            {point.text}{" "}
            <span className="text-xs text-fg-muted">
              {point.single_opinion ? "(نظر یک مهمان: " : "(بر اساس "}
              {point.review_ids.map((id, index) => (
                <span key={id}>
                  {index > 0 ? "، " : ""}
                  <a
                    href={`#${reviewAnchor(id)}`}
                    className="focus-ring rounded-sm text-accent underline underline-offset-4"
                  >
                    نظر {faNumber(order[id] ?? index + 1)}
                  </a>
                </span>
              ))}
              )
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A summary's pros and cons; each point links to the reviews it cites (``order`` numbers them). */
export function SummaryCard({
  summary,
  order,
  title,
}: {
  summary: Summary | null;
  order: Record<string, number>;
  title?: string;
}) {
  if (!summary || (summary.pros.length === 0 && summary.cons.length === 0)) return null;
  return (
    <section
      aria-labelledby="summary-title"
      className="rounded-card border border-line bg-sunken p-5"
    >
      <div className="flex items-center gap-2">
        <Sparkles aria-hidden="true" className="size-5 text-brand-700" />
        <h3 id="summary-title" className="font-semibold text-balance">
          {title ?? `خلاصه‌ی ${faNumber(summary.reviews_given)} نظر اخیر`}
        </h3>
        <Badge tone="muted" className="ms-auto">
          <Quote aria-hidden="true" className="size-3" />
          با ارجاع
        </Badge>
      </div>
      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        <SummaryList
          title="خوب‌ها"
          icon={<ThumbsUp aria-hidden="true" className="size-4 text-brand-700" />}
          points={summary.pros}
          order={order}
        />
        <SummaryList
          title="ایرادها"
          icon={<ThumbsDown aria-hidden="true" className="size-4 text-amber-700" />}
          points={summary.cons}
          order={order}
        />
      </div>
      <p className="mt-4 text-xs text-fg-muted">
        هر نکته به نظرهایی که آن را گفته‌اند پیوند دارد؛ متن خلاصه را مدل زبانی نوشته و پیش از نمایش
        بررسی شده است.
      </p>
    </section>
  );
}

/** The summary is optional: unavailable is said in calm words, never shown as an error. */
export function SummaryUnavailable() {
  return (
    <Callout kind="degraded" title="خلاصه‌ی نظرها فعلاً در دسترس نیست">
      مدل زبانی که خلاصه را می‌نویسد در دسترس نیست و این خلاصه از قبل در حافظه نبود. خود نظرها در
      پایین کامل‌اند.
    </Callout>
  );
}

/** A summary as the API answered: present, absent (too few reviews), or unavailable (503). */
export type SummaryOutcome = { summary: Summary | null; unavailable: boolean };

export async function fetchListingSummary(platform: string, id: string): Promise<SummaryOutcome> {
  try {
    const { data, response } = await apiClient().GET(
      "/listings/{platform}/{external_id}/review-summary",
      { params: { path: { platform, external_id: id } }, cache: "no-store" },
    );
    return { summary: data ?? null, unavailable: response.status === 503 };
  } catch {
    return { summary: null, unavailable: false };
  }
}

/** Pros and cons that cite their reviews; streamed in after the page (one cached LLM call). */
export async function ReviewSummarySection({
  platform,
  id,
  order,
}: {
  platform: string;
  id: string;
  order: Record<string, number>;
}) {
  const outcome = await fetchListingSummary(platform, id);
  if (outcome.unavailable) return <SummaryUnavailable />;
  return <SummaryCard summary={outcome.summary} order={order} />;
}

export function ReviewSummarySkeleton() {
  return (
    <div role="status" className="rounded-card border border-line bg-sunken p-5">
      <span className="sr-only">در حال آماده کردن خلاصه‌ی نظرها…</span>
      <Skeleton className="h-5 w-48" />
      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/5" />
        </div>
      </div>
    </div>
  );
}
