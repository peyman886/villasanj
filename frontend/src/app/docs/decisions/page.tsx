import { ArrowUpLeft, Scale } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { DocHeader } from "@/components/docs/blocks";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { ADR_CARDS } from "@/content/adrs";
import { faInt } from "@/lib/format";
import { loadAdrs } from "@/lib/project-files";

export const metadata: Metadata = {
  title: "تصمیم‌ها (ADR)",
  description: "تصمیم‌های معماری ویلاسنج با زمینه، گزینه‌ها، پیامدها و اصلاحیه‌هایشان.",
};
export const dynamic = "force-dynamic";

export default async function DecisionsPage() {
  const adrs = await loadAdrs();
  const areas = [...new Set(adrs.map((a) => ADR_CARDS[a.number]?.area ?? "دیگر"))];
  return (
    <>
      <DocHeader eyebrow="وضعیت پروژه" title="تصمیم‌های معماری (ADR)">
        هر تصمیمی که برگرداندنش گران است یک ADR دارد: زمینه، تصمیم، گزینه‌های سنجیده‌شده و پیامدها.
        ADR برای برگرداندن تصمیم ویرایش نمی‌شود؛ اندازه‌گیری‌های بعدی به‌صورت اصلاحیه‌ی تاریخ‌دار به
        انتهایش اضافه می‌شوند. متن کامل هر ADR همان فایل مخزن است، به انگلیسی.
      </DocHeader>
      {adrs.length === 0 ? (
        <Callout kind="caution" title="پوشه‌ی docs/adr خوانده نشد">
          متغیر <code className="ltr font-mono">DOCS_DIR</code> را بررسی کنید.
        </Callout>
      ) : null}
      <div className="space-y-10">
        {areas.map((area) => (
          <section key={area} aria-labelledby={`area-${area}`}>
            <h2 id={`area-${area}`} className="mb-3 text-lg font-semibold text-fg">
              {area}
            </h2>
            <ul className="grid gap-3 md:grid-cols-2">
              {adrs
                .filter((a) => (ADR_CARDS[a.number]?.area ?? "دیگر") === area)
                .map((a) => {
                  const card = ADR_CARDS[a.number];
                  const superseded = /superseded/i.test(a.status);
                  return (
                    <li key={a.slug}>
                      <Link
                        href={`/docs/decisions/${a.slug}`}
                        className="focus-ring group flex h-full flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-raised transition-shadow duration-150 hover:shadow-float"
                      >
                        <span className="flex flex-wrap items-center gap-2">
                          <Scale aria-hidden="true" className="size-4 text-accent" />
                          <span className="ltr font-mono text-sm font-semibold text-accent">
                            ADR-{a.number}
                          </span>
                          <Badge tone={superseded ? "caution" : "verified"}>
                            {superseded ? "بخشی جایگزین شده" : "پذیرفته"}
                          </Badge>
                          {a.amendments.length ? (
                            <Badge tone="muted">{faInt(a.amendments.length)} اصلاحیه</Badge>
                          ) : null}
                        </span>
                        <span className="font-semibold text-balance text-fg">
                          {card?.title_fa ?? a.title}
                        </span>
                        <span className="text-sm leading-7 text-pretty text-fg-muted">
                          {card?.summary_fa}
                        </span>
                        <span className="ltr mt-auto block text-xs text-fg-subtle">{a.title}</span>
                        <span className="inline-flex items-center gap-1 text-sm text-accent">
                          خواندن
                          <ArrowUpLeft aria-hidden="true" className="size-3.5" />
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
