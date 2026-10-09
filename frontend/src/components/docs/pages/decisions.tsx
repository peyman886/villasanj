import { ArrowUpLeft, ArrowUpRight, Scale } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { DocHeader } from "@/components/docs/blocks";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { ADR_CARDS, type AdrCard } from "@/content/adrs";
import { formatFor } from "@/lib/format";
import { docsHref, t, type Locale } from "@/lib/i18n";
import { loadAdrs } from "@/lib/project-files";

export function decisionsMetadata(locale: Locale): Metadata {
  return {
    title: t(locale, "تصمیم‌های معماری", "Decisions (ADRs)"),
    description: t(
      locale,
      "تصمیم‌های معماری ویلاسنج با زمینه، گزینه‌ها، پیامدها و اصلاحیه‌هایشان.",
      "Villasanj's architecture decisions with their context, options, consequences and amendments.",
    ),
  };
}

const areaOf = (card: AdrCard | undefined, locale: Locale) =>
  (locale === "en" ? card?.area_en : card?.area) ?? t(locale, "دیگر", "Other");

/** Every ADR as a card, grouped by area. */
export async function DecisionsPage({ locale }: { locale: Locale }) {
  const f = formatFor(locale);
  const en = locale === "en";
  const More = en ? ArrowUpRight : ArrowUpLeft;
  const adrs = await loadAdrs();
  const areas = [...new Set(adrs.map((a) => areaOf(ADR_CARDS[a.number], locale)))];
  return (
    <>
      <DocHeader
        eyebrow={t(locale, "وضعیت پروژه", "Project status")}
        title={t(locale, "تصمیم‌های معماری", "Decisions (ADRs)")}
      >
        {en
          ? "Every decision that is expensive to reverse has an ADR: context, decision, the options weighed and the consequences. An ADR is never edited to reverse a decision; later measurements are appended as dated amendments. The full text of each ADR is the repository file, shown as written."
          : "هر تصمیمی که برگرداندنش گران است یک ADR دارد: زمینه، تصمیم، گزینه‌های سنجیده‌شده و پیامدها. ADR را برای برگرداندن تصمیم ویرایش نمی‌کنیم؛ اندازه‌گیری‌های بعدی به‌صورت اصلاحیه‌ی تاریخ‌دار به انتهایش اضافه می‌شوند. متن کامل هر ADR همان فایل مخزن است، به انگلیسی."}
      </DocHeader>
      {adrs.length === 0 ? (
        <Callout
          kind="caution"
          title={t(locale, "پوشه‌ی docs/adr خوانده نشد", "The docs/adr folder could not be read")}
        >
          {t(locale, "متغیر ", "Check the ")}
          <code className="ltr font-mono">DOCS_DIR</code>
          {t(locale, " را بررسی کنید.", " variable.")}
        </Callout>
      ) : null}
      <div className="space-y-10">
        {areas.map((area, i) => (
          <section key={area} aria-labelledby={`area-${i}`}>
            <h2 id={`area-${i}`} className="mb-3 text-lg font-semibold text-fg">
              {area}
            </h2>
            <ul className="grid gap-3 md:grid-cols-2">
              {adrs
                .filter((a) => areaOf(ADR_CARDS[a.number], locale) === area)
                .map((a) => {
                  const card = ADR_CARDS[a.number];
                  const superseded = /superseded/i.test(a.status);
                  return (
                    <li key={a.slug}>
                      <Link
                        href={docsHref(`/docs/decisions/${a.slug}`, locale)}
                        className="focus-ring group flex h-full flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-raised transition-shadow duration-150 hover:shadow-float"
                      >
                        <span className="flex flex-wrap items-center gap-2">
                          <Scale aria-hidden="true" className="size-4 text-accent" />
                          <span className="ltr font-mono text-sm font-semibold text-accent">
                            ADR-{a.number}
                          </span>
                          <Badge tone={superseded ? "caution" : "verified"}>
                            {superseded
                              ? t(locale, "بخشی جایگزین شده", "Partly superseded")
                              : t(locale, "پذیرفته", "Accepted")}
                          </Badge>
                          {a.amendments.length ? (
                            <Badge tone="muted">
                              {t(
                                locale,
                                `${f.int(a.amendments.length)} اصلاحیه`,
                                `${f.int(a.amendments.length)} ${a.amendments.length === 1 ? "amendment" : "amendments"}`,
                              )}
                            </Badge>
                          ) : null}
                        </span>
                        <span className="font-semibold text-balance text-fg">
                          {(en ? card?.title_en : card?.title_fa) ?? a.title}
                        </span>
                        <span className="text-sm leading-7 text-pretty text-fg-muted">
                          {en ? card?.summary_en : card?.summary_fa}
                        </span>
                        <span className="ltr mt-auto block text-xs text-fg-subtle">{a.title}</span>
                        <span className="inline-flex items-center gap-1 text-sm text-accent">
                          {t(locale, "خواندن", "Read")}
                          <More aria-hidden="true" className="size-3.5" />
                        </span>
                      </Link>
                    </li>
                  );
                })}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}
