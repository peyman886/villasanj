import { FileText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { DocHeader } from "@/components/docs/blocks";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { reportName } from "@/components/ui/source";
import { loadArtifacts } from "@/lib/artifacts";
import { formatFor } from "@/lib/format";
import { docsHref, t, type Locale } from "@/lib/i18n";
import { listReports } from "@/lib/project-files";

export function reportsMetadata(locale: Locale): Metadata {
  return {
    title: t(locale, "گزارش‌های تولیدشده", "Generated reports"),
    description: t(
      locale,
      "همه‌ی گزارش‌های ارزیابی، فرضیه‌ها، کیفیت و کارایی با فرمان و زمان تولید.",
      "Every evaluation, hypothesis, quality and performance report with the command and time that produced it.",
    ),
  };
}

/** The report family: the file name without its date (and model, for judge evaluations). */
function family(name: string): string {
  return name.replace(/-\d{4}-\d{2}-\d{2}.*$/, "");
}

function dateOf(name: string): string | null {
  return /(\d{4}-\d{2}-\d{2})/.exec(name)?.[1] ?? null;
}

/** Every report in reports/, newest of each family marked. */
export async function ReportsPage({ locale }: { locale: Locale }) {
  const f = formatFor(locale);
  const [names, artifacts] = await Promise.all([listReports(), loadArtifacts()]);
  const byName = new Map(
    artifacts.map((a) => [a.file.replace("reports/", "").replace(/\.json$/, ""), a]),
  );
  const newestOfFamily = new Map<string, string>();
  for (const name of names) {
    const fam = family(name);
    const current = newestOfFamily.get(fam);
    if (!current || (dateOf(name) ?? "") > (dateOf(current) ?? "")) newestOfFamily.set(fam, name);
  }
  return (
    <>
      <DocHeader
        eyebrow={t(locale, "وضعیت پروژه", "Project status")}
        title={t(locale, "گزارش‌های تولیدشده", "Generated reports")}
      >
        {t(
          locale,
          "هر عددی که در مستندات و صفحه‌ی اصلی می‌بینید از یکی از این گزارش‌ها می‌آید. هر گزارش را یک فرمان از پایگاه داده ساخته و فرمان، زمان تولید و داده‌ی پایه‌اش (match run، dataset hash، برچسب‌ها) همراهش است. گزارش‌های قدیمی‌تر پاک نمی‌شوند و به‌عنوان تاریخچه می‌مانند.",
          "Every number in the documentation and on the home page comes from one of these reports. Each report was produced by a command from the database, and carries the command, the time of generation and its inputs (match run, dataset hash, labels). Older reports are not deleted; they stay as history.",
        )}
      </DocHeader>
      {names.length === 0 ? (
        <Callout
          kind="caution"
          title={t(locale, "پوشه‌ی reports خوانده نشد", "The reports folder could not be read")}
        >
          {t(locale, "متغیر ", "Check the ")}
          <code className="ltr font-mono">REPORTS_DIR</code>
          {t(locale, " را بررسی کنید.", " variable.")}
        </Callout>
      ) : null}
      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        {names.map((name) => {
          const artifact = byName.get(name);
          const latest = newestOfFamily.get(family(name)) === name;
          return (
            <li key={name}>
              <Link
                href={docsHref(`/docs/reports/${name}`, locale)}
                className="focus-ring flex flex-wrap items-center gap-x-4 gap-y-1 p-4 hover:bg-sunken"
              >
                <FileText aria-hidden="true" className="size-4 shrink-0 text-fg-muted" />
                <span className="font-medium text-fg">
                  {reportName(`reports/${name}.md`, locale)}
                </span>
                <span className="ltr font-mono text-xs text-fg-muted">{name}.md</span>
                <span className="ms-auto flex flex-wrap items-center gap-2">
                  {artifact ? (
                    <Badge tone="brand">
                      {t(locale, "داده‌ی ماشین‌خوان", "Machine-readable data")}
                    </Badge>
                  ) : null}
                  {latest ? (
                    <Badge tone="verified">{t(locale, "جدیدترین", "Latest")}</Badge>
                  ) : (
                    <Badge tone="muted">{t(locale, "تاریخچه", "History")}</Badge>
                  )}
                  {artifact ? (
                    <span className="text-xs text-fg-muted">{f.when(artifact.generated_at)}</span>
                  ) : null}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </>
  );
}
