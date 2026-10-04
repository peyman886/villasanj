import { ImageOff } from "lucide-react";

import { cn } from "@/lib/cn";
import { faNumber } from "@/lib/listing";

const MAX_PHOTOS = 5;

/**
 * The listing's own photos, hotlinked from the platform (no copy on our server). A mosaic on
 * wide screens, a swipeable strip on phones; without network the tiles stay as calm placeholders.
 */
export function Gallery({ photos, platformName }: { photos: string[]; platformName: string }) {
  const shown = photos.slice(0, MAX_PHOTOS);
  if (shown.length === 0) {
    return (
      <div className="grid aspect-[3/1] place-items-center rounded-card border border-dashed border-line-strong bg-sunken text-sm text-fg-muted">
        <span className="flex items-center gap-2">
          <ImageOff aria-hidden="true" className="size-5" />
          این آگهی عکسی منتشر نکرده است.
        </span>
      </div>
    );
  }
  return (
    <section aria-label="عکس‌ها">
      <ul className="flex snap-x snap-mandatory gap-2 overflow-x-auto pb-1 md:grid md:grid-cols-4 md:grid-rows-2 md:overflow-visible">
        {shown.map((url, index) => (
          <li
            key={url}
            className={cn(
              "w-[85%] shrink-0 snap-start md:w-auto",
              index === 0 && "md:col-span-2 md:row-span-2",
            )}
          >
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              referrerPolicy="no-referrer"
              className="focus-ring block size-full overflow-hidden rounded-card bg-gradient-to-br from-brand-100 to-sand-200"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server */}
              <img
                src={url}
                alt={`عکس ${faNumber(index + 1)} از ${faNumber(photos.length)}`}
                loading={index === 0 ? "eager" : "lazy"}
                decoding="async"
                referrerPolicy="no-referrer"
                className={cn(
                  "aspect-[4/3] size-full object-cover transition-transform duration-150 hover:scale-[1.02]",
                  index === 0 && "md:aspect-auto",
                )}
              />
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-fg-muted">
        عکس‌ها مستقیم از سرور {platformName} نمایش داده می‌شوند ({faNumber(photos.length)} عکس).
      </p>
    </section>
  );
}
