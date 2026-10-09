import { Maximize2, X } from "lucide-react";

import { DIAGRAMS, DIAGRAM_STYLES } from "@/diagrams/generated";
import {
  DIAGRAMS as DIAGRAMS_EN,
  DIAGRAM_STYLES as DIAGRAM_STYLES_EN,
} from "@/diagrams/generated-en";
import { t, type Locale } from "@/lib/i18n";

/**
 * A diagram rendered at build time from diagrams/<name>.mmd (scripts/render-diagrams.mjs):
 * static SVG with its own title and description, no runtime library, works offline. Wide
 * diagrams scroll inside their frame on phones; the full-size view opens in a native popover.
 */
export function Diagram({
  name,
  caption,
  locale = "fa",
}: {
  name: string;
  caption: string;
  locale?: Locale;
}) {
  const en = locale === "en";
  const diagram = en ? DIAGRAMS_EN[name] : DIAGRAMS[name];
  const styles = en ? DIAGRAM_STYLES_EN : DIAGRAM_STYLES;
  if (!diagram)
    throw new Error(
      `unknown diagram ${name}: add diagrams/${en ? "en/" : ""}${name}.mmd and run npm run diagrams`,
    );
  const id = `diagram-full-${locale}-${name}`;
  // Wide diagrams keep a readable minimum width and scroll inside their frame on phones.
  const box = /viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"/.exec(diagram.svg);
  const naturalWidth = box ? Number(box[1]) : 600;
  return (
    <figure className="my-8">
      {/* One shared theme stylesheet per diagram kind; React hoists it and keeps one copy. */}
      <style href={`villasanj-diagram-${locale}-${diagram.kind}`} precedence="medium">
        {styles[diagram.kind]}
      </style>
      <div className="relative rounded-card border border-line bg-surface p-4 shadow-raised">
        <button
          type="button"
          popoverTarget={id}
          className="focus-ring absolute end-3 top-3 z-10 grid size-8 place-items-center rounded-control border border-line bg-surface text-fg-muted hover:text-fg"
          aria-label={`${t(locale, "نمایش بزرگ", "Full size")}: ${caption}`}
        >
          <Maximize2 aria-hidden="true" className="size-4" />
        </button>
        <div
          className="focus-ring overflow-x-auto rounded-control"
          tabIndex={0}
          role="region"
          aria-label={caption}
        >
          <div
            className="mx-auto [&_svg]:mx-auto [&_svg]:h-auto"
            style={{ minWidth: `${Math.min(naturalWidth, 560) * 0.8}px` }}
            dangerouslySetInnerHTML={{ __html: diagram.svg }}
          />
        </div>
      </div>
      <figcaption className="mt-2 text-center text-sm text-pretty text-fg-muted">
        {caption}
      </figcaption>
      <div
        id={id}
        popover="auto"
        role="dialog"
        aria-label={caption}
        className="m-auto max-h-[92dvh] w-[min(96vw,80rem)] overflow-auto rounded-card border border-line bg-surface p-6 shadow-overlay backdrop:bg-scrim/40"
      >
        <div className="mb-3 flex items-center justify-between gap-4">
          <p className="font-semibold">{caption}</p>
          <button
            type="button"
            popoverTarget={id}
            popoverTargetAction="hide"
            aria-label={t(locale, "بستن", "Close")}
            className="focus-ring grid size-8 place-items-center rounded-control hover:bg-sunken"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        <div
          className="[&_svg]:h-auto [&_svg]:w-full"
          dangerouslySetInnerHTML={{ __html: diagram.svg }}
        />
      </div>
    </figure>
  );
}
