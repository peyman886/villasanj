"use client";

import { usePathname } from "next/navigation";

import { localeOf, type Locale } from "@/lib/i18n";

/** The docs page's language, for the few MDX-wide components that cannot take a prop. */
export function useDocsLocale(): Locale {
  return localeOf(usePathname());
}
