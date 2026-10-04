import { Sourced } from "@/components/sourced";
import { Section } from "@/components/ui/card";
import type { CalendarNight, Listing } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import {
  AVAILABILITY_TEXT,
  WEEKDAY_HEADERS,
  calendarWeeks,
  faDay,
  faDayOfMonth,
  faMillions,
  faNumber,
  faToman,
} from "@/lib/listing";

const CELL_TONE: Record<string, string> = {
  available: "border-brand-200 bg-brand-50 text-brand-950 hover:border-brand-400",
  unknown: "border-line bg-surface text-fg-muted",
};

export function CalendarLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
      <li className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="size-3 rounded-sm border border-brand-300 bg-brand-50"
        />
        آزاد
      </li>
      <li className="flex items-center gap-1.5">
        <span aria-hidden="true" className="size-3 rounded-sm border border-line bg-sunken" />
        پر یا بسته
      </li>
      <li className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className="size-3 rounded-sm border border-dashed border-line-strong"
        />
        بی‌داده
      </li>
      <li>قیمت هر شب به میلیون تومان</li>
    </ul>
  );
}

function NightCell({ night, listing, now }: { night: CalendarNight; listing: Listing; now: Date }) {
  const price = night.price;
  return (
    <Sourced
      id={`night-${night.night}`}
      label={`شب ${faDay(night.night)}`}
      value={[
        AVAILABILITY_TEXT[night.availability] ?? night.availability,
        price ? faToman(price) : "قیمت منتشر نشده",
        night.min_nights ? `حداقل ${faNumber(night.min_nights)} شب` : null,
      ]
        .filter(Boolean)
        .join("، ")}
      provenance={night.provenance}
      sourceName={listing.platform_name}
      now={now}
      className={cn(
        "block min-h-14 w-full rounded-control border p-1 text-center no-underline transition-colors sm:p-1.5",
        CELL_TONE[night.availability] ?? "border-line bg-sunken text-fg-muted",
        night.is_holiday && "ring-1 ring-amber-400 ring-inset",
      )}
    >
      <span className="block font-semibold tabular-nums">{faDayOfMonth(night.night)}</span>
      {price ? (
        <span className="block text-[0.7rem] leading-tight tabular-nums">
          {faMillions(price.low_toman)}
        </span>
      ) : (
        <span className="block text-[0.7rem] leading-tight">
          {AVAILABILITY_TEXT[night.availability] ?? night.availability}
        </span>
      )}
      {night.is_holiday ? (
        <span className="block text-[0.65rem] leading-tight font-medium text-amber-800">تعطیل</span>
      ) : null}
    </Sourced>
  );
}

export function CalendarSection({
  listing,
  nights,
  start,
  days,
  now,
}: {
  listing: Listing;
  nights: CalendarNight[];
  start: string;
  days: number;
  now: Date;
}) {
  const weeks = calendarWeeks(nights, start, days);
  return (
    <Section
      id="calendar"
      title={`تقویم ${faNumber(days)} شب آینده`}
      description="هر خانه آخرین مشاهده‌ی همان شب است، نه وضعیت قطعی؛ مبلغ دقیق در منبع هر خانه آمده. «پر یا بسته» یعنی پلتفرم نگفته رزرو شده یا میزبان بسته است."
    >
      {nights.length === 0 ? (
        <p className="text-sm text-fg-muted">برای این بازه مشاهده‌ای از تقویم نداریم.</p>
      ) : (
        <div className="rounded-card border border-line bg-surface p-3 sm:p-4">
          <CalendarLegend />
          <table className="mt-3 w-full table-fixed border-separate border-spacing-1 text-xs sm:text-sm">
            <caption className="sr-only">تقویم آزاد و پر بودن شب‌ها با قیمت هر شب</caption>
            <thead>
              <tr>
                {WEEKDAY_HEADERS.map((name) => (
                  <th key={name} scope="col" className="py-1 font-normal text-fg-muted">
                    <span aria-hidden="true" className="sm:hidden">
                      {name[0]}
                    </span>
                    <span className="max-sm:sr-only">{name}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weeks.map((week) => (
                <tr key={week.find((c) => c !== null)?.day}>
                  {week.map((cell, index) => (
                    <td key={cell?.day ?? `empty-${index}`} className="p-0 align-top">
                      {cell === null ? null : cell.night === null ? (
                        <div className="min-h-14 rounded-control border border-dashed border-line-strong p-1 text-center text-fg-subtle sm:p-1.5">
                          <span className="block tabular-nums">{faDayOfMonth(cell.day)}</span>
                          <span className="block text-[0.7rem] leading-tight">بی‌داده</span>
                        </div>
                      ) : (
                        <NightCell night={cell.night} listing={listing} now={now} />
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}
