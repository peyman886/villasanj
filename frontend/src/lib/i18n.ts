/**
 * The documentation portal exists in two languages: Persian at /docs (right to left) and English
 * at /en/docs (left to right), page for page. The product itself is Persian only.
 */
export type Locale = "fa" | "en";

export const LOCALES: Locale[] = ["fa", "en"];

/** The portal's root for a language: "/docs" or "/en/docs". */
export function docsRoot(locale: Locale): string {
  return locale === "en" ? "/en/docs" : "/docs";
}

/** A docs path ("/docs/pricing", "/docs") in the given language. */
export function docsHref(path: string, locale: Locale): string {
  const bare = path.replace(/^\/en(?=\/docs)/, "");
  return locale === "en" && bare.startsWith("/docs") ? `/en${bare}` : bare;
}

/** The language a path belongs to. */
export function localeOf(path: string): Locale {
  return path === "/en" || path.startsWith("/en/") ? "en" : "fa";
}

/** Pick the string for a language: t(locale, "فارسی", "English"). */
export function t(locale: Locale, fa: string, en: string): string {
  return locale === "en" ? en : fa;
}
