import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DocHeader } from "@/components/docs/blocks";
import { Markdown } from "@/components/docs/markdown";
import { Badge } from "@/components/ui/badge";
import { ADR_CARDS } from "@/content/adrs";
import { formatFor } from "@/lib/format";
import { docsHref, t, type Locale } from "@/lib/i18n";
import { loadAdr, loadAdrs } from "@/lib/project-files";

export async function decisionMetadata(slug: string, locale: Locale): Promise<Metadata> {
  const adr = await loadAdr(slug);
  if (!adr) return { title: t(locale, "تصمیم پیدا نشد", "Decision not found") };
  const card = ADR_CARDS[adr.number];
  const title = (locale === "en" ? card?.title_en : card?.title_fa) ?? adr.title;
  return {
    title: `ADR-${adr.number}: ${title}`,
    description: locale === "en" ? card?.summary_en : card?.summary_fa,
  };
}

/** One ADR: the card's title and summary, its amendments, and the file as written (English). */
export async function DecisionPage({ slug, locale }: { slug: string; locale: Locale }) {
  const adr = await loadAdr(slug);
  if (!adr) notFound();
  const f = formatFor(locale);
  const en = locale === "en";
  const card = ADR_CARDS[adr.number];
  const all = await loadAdrs();
  const index = all.findIndex((a) => a.slug === adr.slug);
  const previous = index > 0 ? all[index - 1] : undefined;
  const next = index >= 0 && index < all.length - 1 ? all[index + 1] : undefined;
  const href = (path: string) => docsHref(path, locale);
  // The ADR's own H1 is replaced by the page header; the rest is shown as written.
  const body = adr.body.replace(/^#\s+.+\n/, "");
  return (
    <>
      <DocHeader
        eyebrow={t(locale, `تصمیم‌ها · ADR-${adr.number}`, `Decisions · ADR-${adr.number}`)}
        title={(en ? card?.title_en : card?.title_fa) ?? adr.title}
        meta={
          <>
            <Badge tone="verified">{t(locale, "پذیرفته", "Accepted")}</Badge>
            {adr.amendments.length ? (
              <Badge tone="muted">
                {t(
                  locale,
                  `${f.int(adr.amendments.length)} اصلاحیه`,
                  `${f.int(adr.amendments.length)} ${adr.amendments.length === 1 ? "amendment" : "amendments"}`,
                )}
              </Badge>
            ) : null}
            <span className="ltr text-xs text-fg-muted">{adr.title}</span>
          </>
        }
      >
        {en ? card?.summary_en : card?.summary_fa}
      </DocHeader>
      {adr.amendments.length ? (
        <nav
          aria-label={t(locale, "اصلاحیه‌ها", "Amendments")}
          className="mb-8 rounded-card border border-line bg-sunken p-4"
        >
          <p className="text-sm font-semibold text-fg">
            {t(locale, "اصلاحیه‌ها، به ترتیب زمان", "Amendments, in order")}
          </p>
          <ol className="ltr mt-2 list-decimal space-y-1 ps-6 text-start text-sm text-fg-muted">
            {adr.amendments.map((a) => (
              <li key={a.title}>{a.title}</li>
            ))}
          </ol>
        </nav>
      ) : null}
      <Markdown dir="ltr" lang="en" className="text-start" locale={locale}>
        {body}
      </Markdown>
      <nav
        aria-label={t(locale, "ADR قبلی و بعدی", "Previous and next ADR")}
        className="mt-12 flex flex-wrap justify-between gap-3 border-t border-line pt-6 text-sm"
      >
        {previous ? (
          <Link
            className="focus-ring rounded-sm text-accent hover:underline"
            href={href(`/docs/decisions/${previous.slug}`)}
          >
            {en ? `← ADR-${previous.number}` : `→ ADR-${previous.number}`}
          </Link>
        ) : (
          <span />
        )}
        <Link
          className="focus-ring rounded-sm text-accent hover:underline"
          href={href("/docs/decisions")}
        >
          {t(locale, "همه‌ی تصمیم‌ها", "All decisions")}
        </Link>
        {next ? (
          <Link
            className="focus-ring rounded-sm text-accent hover:underline"
            href={href(`/docs/decisions/${next.slug}`)}
          >
            {en ? `ADR-${next.number} →` : `ADR-${next.number} ←`}
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </>
  );
}
