import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { DocHeader } from "@/components/docs/blocks";
import { Markdown } from "@/components/docs/markdown";
import { CodeBlock } from "@/components/docs/prose";
import { reportName } from "@/components/ui/source";
import { loadArtifacts } from "@/lib/artifacts";
import { formatFor } from "@/lib/format";
import { docsHref, t, type Locale } from "@/lib/i18n";
import { readReport } from "@/lib/project-files";

export function reportMetadata(name: string, locale: Locale): Metadata {
  return { title: `${reportName(`reports/${name}.md`, locale)} · ${name}` };
}

function value(v: unknown): string {
  if (Array.isArray(v)) return v.map(String).join(" → ");
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** One report: its provenance (when there is a JSON artifact) and the markdown as written. */
export async function ReportPage({ name, locale }: { name: string; locale: Locale }) {
  const text = await readReport(name);
  if (text === null) notFound();
  const f = formatFor(locale);
  const artifact = (await loadArtifacts()).find((a) => a.file === `reports/${name}.json`);
  const body = text.replace(/^#\s+.+\n/, "");
  const title = /^#\s+(.+)$/m.exec(text)?.[1];
  return (
    <>
      <DocHeader
        eyebrow={t(locale, "گزارش‌های تولیدشده", "Generated reports")}
        title={reportName(`reports/${name}.md`, locale)}
        meta={<span className="ltr font-mono text-xs text-fg-muted">reports/{name}.md</span>}
      >
        {title ? <span className="ltr block text-base">{title}</span> : null}
      </DocHeader>
      {artifact ? (
        <section
          aria-labelledby="provenance"
          className="mb-10 rounded-card border border-line bg-sunken p-4"
        >
          <h2 id="provenance" className="font-semibold text-fg">
            {t(locale, "منبع این گزارش", "Provenance of this report")}
          </h2>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[10rem_minmax(0,1fr)]">
            <dt className="text-fg-muted">{t(locale, "زمان تولید", "Generated")}</dt>
            <dd>{f.when(artifact.generated_at)}</dd>
            <dt className="text-fg-muted">
              {t(locale, "داده‌ی ماشین‌خوان", "Machine-readable data")}
            </dt>
            <dd className="ltr font-mono text-xs">{artifact.file}</dd>
            {Object.entries(artifact.provenance).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="ltr text-start font-mono text-xs text-fg-muted">{k}</dt>
                <dd className="ltr font-mono text-xs break-all">{value(v)}</dd>
              </div>
            ))}
          </dl>
          <CodeBlock title={t(locale, "بازتولید", "Reproduce")}>
            <code>{artifact.command}</code>
          </CodeBlock>
        </section>
      ) : null}
      <Markdown dir="ltr" lang="en" className="text-start" locale={locale}>
        {body}
      </Markdown>
      <p className="mt-12 border-t border-line pt-6 text-sm">
        <Link
          className="focus-ring rounded-sm text-accent hover:underline"
          href={docsHref("/docs/reports", locale)}
        >
          {t(locale, "همه‌ی گزارش‌ها", "All reports")}
        </Link>
      </p>
    </>
  );
}
