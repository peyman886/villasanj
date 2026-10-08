import { Images, ImageOff } from "lucide-react";

import { cn } from "@/lib/cn";
import { dedupeGallery, type GalleryPhoto } from "@/lib/gallery";
import { faNum } from "@/lib/numbers";

const MOSAIC = 5;

function Photo({ photo, index, total }: { photo: GalleryPhoto; index: number; total: number }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element -- hotlinked on purpose: no copy on our server
    <img
      src={photo.url}
      alt={`عکس ${faNum(index + 1)} از ${faNum(total)}`}
      loading={index === 0 ? "eager" : "lazy"}
      decoding="async"
      referrerPolicy="no-referrer"
      className="size-full object-cover"
    />
  );
}

/**
 * One large photo and four small ones, the other platform's copies of the same photo removed by
 * perceptual hash (V1). «+N عکس» opens every remaining photo. Photos are hotlinked; without
 * network the tiles stay as calm placeholders.
 */
export function VillaGallery({ gallery }: { gallery: GalleryPhoto[] }) {
  const photos = dedupeGallery(gallery);
  if (photos.length === 0) {
    return (
      <div className="grid aspect-[3/1] place-items-center rounded-card border border-dashed border-line-strong bg-sunken text-sm text-fg-muted">
        <span className="flex items-center gap-2">
          <ImageOff aria-hidden="true" className="size-5" />
          این ویلا عکسی منتشر نکرده است.
        </span>
      </div>
    );
  }
  const shown = photos.slice(0, MOSAIC);
  const more = photos.length - shown.length;
  return (
    <section aria-label="عکس‌ها" className="relative">
      <ul
        data-gallery=""
        className="flex snap-x snap-mandatory gap-2 overflow-x-auto md:grid md:aspect-[12/5] md:grid-cols-4 md:grid-rows-2 md:overflow-visible"
      >
        {shown.map((photo, index) => (
          <li
            key={photo.url}
            data-phash={photo.phash ?? undefined}
            className={cn(
              "aspect-[4/3] w-[85%] shrink-0 snap-start overflow-hidden bg-gradient-to-br from-brand-100 to-sand-200 md:aspect-auto md:w-auto",
              index === 0 && "md:col-span-2 md:row-span-2 md:rounded-s-card",
              index === 2 && "md:rounded-se-card",
              index === 4 && "md:rounded-ee-card",
              "max-md:rounded-card",
            )}
          >
            <Photo photo={photo} index={index} total={photos.length} />
          </li>
        ))}
      </ul>
      {more > 0 ? (
        <>
          <button
            type="button"
            popoverTarget="all-photos"
            className="focus-ring absolute end-3 bottom-3 inline-flex items-center gap-1.5 rounded-control bg-surface/95 px-3 py-1.5 text-sm font-medium shadow-raised hover:bg-surface"
          >
            <Images aria-hidden="true" className="size-4" />+{faNum(more)} عکس
          </button>
          <div
            id="all-photos"
            popover="auto"
            role="dialog"
            aria-label="همه‌ی عکس‌ها"
            className="m-auto max-h-[85dvh] w-[min(64rem,calc(100vw-2rem))] overflow-y-auto rounded-modal border border-line bg-surface p-4 shadow-overlay backdrop:bg-sand-950/40"
          >
            <div className="flex items-center justify-between">
              <p className="font-semibold">همه‌ی {faNum(photos.length)} عکس</p>
              <button
                type="button"
                popoverTarget="all-photos"
                popoverTargetAction="hide"
                className="focus-ring rounded-control border border-line-strong px-3 py-1 text-sm hover:bg-sunken"
              >
                بستن
              </button>
            </div>
            <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {photos.map((photo, index) => (
                <li
                  key={photo.url}
                  className="aspect-[4/3] overflow-hidden rounded-control bg-sunken"
                >
                  <Photo photo={photo} index={index} total={photos.length} />
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </section>
  );
}
