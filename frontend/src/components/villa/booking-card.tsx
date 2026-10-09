import { CalendarDays, Minus, Plus, Users } from "lucide-react";
import Link from "next/link";

import { Sourced } from "@/components/sourced";
import { SplitCalendar } from "@/components/villa/split-calendar";
import type { Listing, Offer } from "@/lib/api/client";
import { availabilityText, bookingRows, unavailableText } from "@/lib/booking";
import { faDay, daysBetween, type VillaNight } from "@/lib/calendar";
import { cn } from "@/lib/cn";
import { COPY, priceAge, seeOn } from "@/lib/copy";
import { faAge } from "@/lib/listing";
import { faNum, perPerson, priceFrom, priceFull } from "@/lib/numbers";
import { toneOf } from "@/lib/platforms";

export type Stay = { checkIn: string; checkOut: string; guests: number };

function stayHref(stay: Stay, guests: number): string {
  const q = new URLSearchParams({ in: stay.checkIn, out: stay.checkOut, guests: String(guests) });
  return `?${q}#booking`;
}

/**
 * The sticky booking card (M12 1.6, «پلتفرم‌ها»): the stay and the group, inherited from the
 * search and editable here, then each platform's own price for exactly that stay, the cheaper
 * first, each with its own age and a link out. The fee caveat is said here and nowhere else on
 * the page. Changing the stay re-quotes from stored observations; no platform is asked live.
 */
export function BookingCard({
  members,
  offers,
  stay,
  maxGuests,
  nights,
  calendar,
  now,
}: {
  members: Listing[];
  offers: Offer[];
  stay: Stay;
  maxGuests: number;
  nights: VillaNight[];
  calendar: { start: string; days: number };
  now: Date;
}) {
  const rows = bookingRows(members, offers);
  const count = daysBetween(stay.checkIn, stay.checkOut);
  const names = Object.fromEntries(members.map((m) => [m.platform, m.platform_name]));
  const hidden = nights.filter(
    (n) => n.hidden && n.night >= stay.checkIn && n.night < stay.checkOut,
  ).length;
  const newest = rows
    .map((r) => r.offer?.provenance.oldest_input_at)
    .filter((x): x is string => Boolean(x))
    .sort()
    .at(-1);
  return (
    <div
      id="booking"
      className="scroll-mt-24 rounded-card border border-line bg-surface p-5 shadow-float"
    >
      <h2 className="sr-only">قیمت در پلتفرم‌ها</h2>
      <div className="grid gap-2">
        <button
          type="button"
          popoverTarget="stay-picker"
          className="focus-ring flex items-center gap-2 rounded-control border border-line-strong px-3 py-2 text-start text-sm hover:border-sand-500"
        >
          <CalendarDays aria-hidden="true" className="size-4 shrink-0 text-fg-muted" />
          <span className="min-w-0">
            <span className="block truncate font-medium">
              {faDay(stay.checkIn)} تا {faDay(stay.checkOut)}
            </span>
            <span className="block text-xs text-fg-muted">{faNum(count)} شب · تغییر تاریخ</span>
          </span>
        </button>
        <div
          role="group"
          aria-label="تعداد نفر"
          className="flex items-center gap-1 rounded-control border border-line-strong px-3 py-1"
        >
          <Users aria-hidden="true" className="size-4 text-fg-muted" />
          <span className="me-auto text-sm text-fg-muted">مهمان‌ها</span>
          <Link
            href={stayHref(stay, Math.max(1, stay.guests - 1))}
            scroll={false}
            aria-label="یک نفر کمتر"
            aria-disabled={stay.guests <= 1}
            className={cn(
              "focus-ring grid size-7 place-items-center rounded-full hover:bg-sunken",
              stay.guests <= 1 && "pointer-events-none opacity-40",
            )}
          >
            <Minus aria-hidden="true" className="size-3.5" />
          </Link>
          <span
            className="min-w-10 text-center text-sm font-medium tabular-nums"
            aria-live="polite"
          >
            {faNum(stay.guests)} نفر
          </span>
          <Link
            href={stayHref(stay, Math.min(maxGuests, stay.guests + 1))}
            scroll={false}
            aria-label="یک نفر بیشتر"
            aria-disabled={stay.guests >= maxGuests}
            className={cn(
              "focus-ring grid size-7 place-items-center rounded-full hover:bg-sunken",
              stay.guests >= maxGuests && "pointer-events-none opacity-40",
            )}
          >
            <Plus aria-hidden="true" className="size-3.5" />
          </Link>
        </div>
      </div>
      <div
        id="stay-picker"
        popover="auto"
        role="dialog"
        aria-label="انتخاب تاریخ ورود و خروج"
        className="m-auto w-[min(40rem,calc(100vw-2rem))] rounded-modal border border-line bg-surface p-4 shadow-overlay backdrop:bg-scrim/30"
      >
        <p className="mb-2 text-sm text-fg-muted">روز ورود و سپس روز خروج را انتخاب کنید.</p>
        <SplitCalendar
          compact
          nights={nights}
          names={names}
          start={calendar.start}
          days={calendar.days}
          checkIn={stay.checkIn}
          checkOut={stay.checkOut}
          guests={stay.guests}
          nowIso={now.toISOString()}
        />
      </div>

      <p className="mt-4 text-sm">
        {availabilityText(rows)}
        {newest ? <span className="text-fg-muted"> · {faAge(newest, now)}</span> : null}
      </p>
      {hidden > 0 ? (
        <p className="mt-2 rounded-control px-3 py-1.5 text-sm ring-2 ring-hidden">
          {faNum(hidden)} شب از این سفر «شب پنهان» است: در یک پلتفرم ناموجود و در دیگری خالی دیده
          شده.
        </p>
      ) : null}

      <h3 className="mt-4 text-sm font-semibold text-fg-muted">{COPY.platforms}</h3>
      <ul className="mt-2 divide-y divide-line" data-booking-rows="">
        {rows.map((row) => {
          const offer = row.offer;
          const total = row.bookable ? offer?.total : null;
          const extra = offer?.nights[0]?.extra_guests ?? 0;
          return (
            <li
              key={row.listing.id}
              data-platform={row.listing.platform}
              className={cn("py-3 first:pt-0", !row.bookable && "text-fg-muted")}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 font-medium">
                  <span
                    aria-hidden="true"
                    className={cn("size-2.5 rounded-full", toneOf(row.listing.platform).solid)}
                  />
                  {row.listing.platform_name}
                </span>
                {row.cheaper ? (
                  <span className="rounded-full bg-brand-50 px-2 text-xs font-semibold text-brand-800">
                    {COPY.cheaper}
                  </span>
                ) : null}
              </div>
              {total && offer ? (
                <>
                  <p className="mt-1 text-lg font-bold tabular-nums">
                    <Sourced
                      quiet
                      id={`booking-${row.listing.platform}`}
                      label={`قیمت ${faNum(count)} شب برای ${faNum(stay.guests)} نفر در ${row.listing.platform_name}`}
                      value={priceFull(total)}
                      provenance={offer.provenance}
                      sourceName={row.listing.platform_name}
                      now={now}
                    >
                      {priceFull(total)}
                    </Sourced>
                  </p>
                  <p className="text-xs text-fg-muted tabular-nums">
                    برای {faNum(count)} شب
                    {extra > 0 ? ` · شامل ${faNum(extra)} نفر اضافه` : ""}
                    {stay.guests > 1 ? ` · ${perPerson(total, stay.guests)}` : ""}
                  </p>
                  <p
                    className={cn(
                      "text-xs tabular-nums",
                      offer.stale ? "text-caution" : "text-fg-subtle",
                    )}
                  >
                    {priceAge(faAge(offer.provenance.oldest_input_at, now))}
                  </p>
                </>
              ) : (
                <p className="mt-1 text-sm">{unavailableText(row, stay.guests)}</p>
              )}
              <a
                href={row.listing.url}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "focus-ring mt-2 inline-flex h-9 items-center rounded-control px-3 text-sm font-semibold transition-colors",
                  row.bookable && rows.indexOf(row) === 0
                    ? "bg-brand-gradient text-white hover:opacity-95"
                    : "border border-line-strong text-fg hover:bg-sunken",
                )}
              >
                {offer?.stale && row.bookable
                  ? `دیدن قیمت امروز در ${row.listing.platform_name} ↗`
                  : seeOn(row.listing.platform_name)}
              </a>
            </li>
          );
        })}
      </ul>
      {members.length === 1 ? (
        <p className="mt-1 text-xs text-fg-muted">
          این ویلا را فقط در {members[0]?.platform_name} پیدا کردیم.
        </p>
      ) : null}
      <p className="mt-3 border-t border-line pt-3 text-xs text-pretty text-fg-muted">
        {COPY.feeVilla}
      </p>
    </div>
  );
}

/**
 * Phones (M12 3.3): the booking card lives at the end of the page, so a bar at the bottom keeps
 * the cheaper platform's own price in view and jumps to «پلتفرم‌ها».
 */
export function MobileBookingBar({
  members,
  offers,
  stay,
}: {
  members: Listing[];
  offers: Offer[];
  stay: Stay;
}) {
  const top = bookingRows(members, offers).find((r) => r.bookable);
  const total = top?.offer?.total;
  return (
    <div
      data-mobile-booking=""
      className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-between gap-3 border-t border-line bg-surface/95 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur lg:hidden"
    >
      <div className="min-w-0">
        {total ? (
          <p className="font-bold tabular-nums">{priceFrom(total)}</p>
        ) : (
          <p className="text-sm text-fg-muted">برای این تاریخ خالی دیده نشد</p>
        )}
        <p className="truncate text-xs text-fg-muted tabular-nums">
          {faNum(daysBetween(stay.checkIn, stay.checkOut))} شب، {faNum(stay.guests)} نفر
          {top ? ` · در ${top.listing.platform_name}` : ""}
        </p>
      </div>
      <a
        href="#booking"
        className="focus-ring inline-flex h-11 shrink-0 items-center rounded-control bg-brand-gradient px-5 font-semibold text-white active:scale-[0.98]"
      >
        {COPY.compareOffers}
      </a>
    </div>
  );
}
