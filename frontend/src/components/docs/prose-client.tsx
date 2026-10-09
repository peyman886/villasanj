"use client";

import { Link as LinkIcon } from "lucide-react";
import type { ReactNode } from "react";

import { useDocsLocale } from "@/components/docs/locale-label";
import { t } from "@/lib/i18n";

/** The hover anchor after a heading, labelled in the page's language. */
export function SectionAnchor({ id }: { id: string }) {
  const locale = useDocsLocale();
  return (
    <a
      href={`#${id}`}
      aria-label={t(locale, "پیوند به این بخش", "Link to this section")}
      className="focus-ring ms-2 inline-flex rounded-sm align-middle text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
    >
      <LinkIcon aria-hidden="true" className="size-4" />
    </a>
  );
}

/** A scrollable table frame (keyboard-scrollable, so it is a labelled region). */
export function TableRegion({ children }: { children: ReactNode }) {
  const locale = useDocsLocale();
  return (
    <div
      className="my-5 overflow-x-auto rounded-card border border-line bg-surface"
      tabIndex={0}
      role="region"
      aria-label={t(locale, "جدول", "Table")}
    >
      {children}
    </div>
  );
}
