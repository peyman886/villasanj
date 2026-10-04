import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DocHeader } from "@/components/docs/blocks";
import { Markdown } from "@/components/docs/markdown";
import { Badge } from "@/components/ui/badge";
import { ADR_CARDS } from "@/content/adrs";
import { faInt } from "@/lib/format";
import { loadAdr, loadAdrs } from "@/lib/project-files";

type Props = { params: Promise<{ slug: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const adr = await loadAdr((await params).slug);
  if (!adr) return { title: "تصمیم پیدا نشد" };
  return {
    title: `ADR-${adr.number}: ${ADR_CARDS[adr.number]?.title_fa ?? adr.title}`,
    description: ADR_CARDS[adr.number]?.summary_fa,
  };
}

export default async function AdrPage({ params }: Props) {
  const adr = await loadAdr((await params).slug);
  if (!adr) notFound();
  const card = ADR_CARDS[adr.number];
  const all = await loadAdrs();
  const index = all.findIndex((a) => a.slug === adr.slug);
  const previous = index > 0 ? all[index - 1] : undefined;
  const next = index >= 0 && index < all.length - 1 ? all[index + 1] : undefined;
  // The ADR's own H1 is replaced by the page header; the rest is shown as written.
  const body = adr.body.replace(/^#\s+.+\n/, "");
  return (
    <>
      <DocHeader
        eyebrow={`تصمیم‌ها · ADR-${adr.number}`}
        title={card?.title_fa ?? adr.title}
        meta={
          <>
            <Badge tone="verified">پذیرفته</Badge>
            {adr.amendments.length ? (
              <Badge tone="muted">{faInt(adr.amendments.length)} اصلاحیه</Badge>
            ) : null}
            <span className="ltr text-xs text-fg-muted">{adr.title}</span>
          </>
        }
      >
        {card?.summary_fa}
      </DocHeader>
      {adr.amendments.length ? (
        <nav aria-label="اصلاحیه‌ها" className="mb-8 rounded-card border border-line bg-sunken p-4">
          <p className="text-sm font-semibold text-fg">اصلاحیه‌ها، به ترتیب زمان</p>
          <ol className="ltr mt-2 list-decimal space-y-1 ps-6 text-start text-sm text-fg-muted">
            {adr.amendments.map((a) => (
              <li key={a.title}>{a.title}</li>
            ))}
          </ol>
        </nav>
      ) : null}
      <Markdown dir="ltr" lang="en" className="text-start">
        {body}
      </Markdown>
      <nav
        aria-label="ADR قبلی و بعدی"
        className="mt-12 flex flex-wrap justify-between gap-3 border-t border-line pt-6 text-sm"
      >
        {previous ? (
          <Link
            className="focus-ring rounded-sm text-accent hover:underline"
            href={`/docs/decisions/${previous.slug}`}
          >
            → ADR-{previous.number}
          </Link>
        ) : (
          <span />
        )}
        <Link className="focus-ring rounded-sm text-accent hover:underline" href="/docs/decisions">
          همه‌ی تصمیم‌ها
        </Link>
        {next ? (
          <Link
            className="focus-ring rounded-sm text-accent hover:underline"
            href={`/docs/decisions/${next.slug}`}
          >
            ADR-{next.number} ←
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </>
  );
}
