import { CarFront, CircleCheck, Star, Waves } from "lucide-react";

import { Sourced } from "@/components/sourced";
import type { Geo } from "@/lib/api/client";
import { distanceRange, durationRange, faNum, rating } from "@/lib/numbers";
import type { Highlight } from "@/lib/truth";

/**
 * 3 to 5 verified facts with their source label (M12 2.1): claims the map or the photos support,
 * the measured distance to the sea and drive time, and the platforms' own ratings. Nothing a
 * host merely says becomes a highlight.
 */
export function Highlights({
  claims,
  geo,
  ratingValue,
  ratingCount,
  platforms,
  now,
}: {
  claims: Highlight[];
  geo: Geo | null;
  ratingValue: number | null;
  ratingCount: number;
  platforms: number;
  now: Date;
}) {
  const items: { key: string; icon: React.ReactNode; text: React.ReactNode; source: string }[] =
    claims.map((h) => ({
      key: h.key,
      icon: <CircleCheck aria-hidden="true" className="size-5 text-verified" />,
      text: h.text,
      source: h.source,
    }));
  if (geo?.coast_m) {
    items.push({
      key: "coast",
      icon: <Waves aria-hidden="true" className="size-5 text-brand-700" />,
      text: (
        <Sourced
          quiet
          id="highlight-coast"
          label="فاصله تا دریا"
          value={geo.coast_m.text}
          provenance={geo.coast_m.provenance}
          now={now}
        >
          {distanceRange(geo.coast_m.low, geo.coast_m.high)} تا دریا
        </Sourced>
      ),
      source: "روی نقشه اندازه‌گیری شد",
    });
  }
  if (geo?.drive_s) {
    items.push({
      key: "drive",
      icon: <CarFront aria-hidden="true" className="size-5 text-brand-700" />,
      text: (
        <Sourced
          quiet
          id="highlight-drive"
          label="زمان رانندگی"
          value={geo.drive_s.text}
          provenance={geo.drive_s.provenance}
          now={now}
        >
          {durationRange(geo.drive_s.low, geo.drive_s.high)} از تهران
        </Sourced>
      ),
      source: "بدون ترافیک، روی نقشه",
    });
  }
  if (ratingValue !== null && ratingCount > 0) {
    items.push({
      key: "rating",
      icon: <Star aria-hidden="true" className="size-5 fill-amber-400 text-amber-500" />,
      text: `${rating(ratingValue)} از ۵ · ${faNum(ratingCount)} امتیاز`,
      source: platforms > 1 ? `در ${faNum(platforms)} پلتفرم` : "امتیاز مهمان‌ها",
    });
  }
  const shown = items.slice(0, 5);
  if (shown.length < 3) return null;
  return (
    <ul
      aria-label="برجسته‌ها"
      data-highlights=""
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      {shown.map((item) => (
        <li key={item.key} data-highlight={item.key} className="flex items-start gap-3">
          <span className="mt-0.5 shrink-0">{item.icon}</span>
          <span>
            <span className="block font-semibold">{item.text}</span>
            <span className="block text-sm text-fg-muted">{item.source}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
