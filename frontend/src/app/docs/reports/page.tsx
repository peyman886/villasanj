import { FileText } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { DocHeader } from "@/components/docs/blocks";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { reportName } from "@/components/ui/source";
import { loadArtifacts } from "@/lib/artifacts";
import { faWhen } from "@/lib/format";
import { listReports } from "@/lib/project-files";

export const metadata: Metadata = {
  title: "گزارش‌های تولیدشده",
  description: "همه‌ی گزارش‌های ارزیابی، فرضیه‌ها، کیفیت و کارایی با فرمان و زمان تولید.",
};
export const dynamic = "force-dynamic";

/** The report family: the file name without its date (and model, for judge evaluations). */
function family(name: string): string {
  return name.replace(/-\d{4}-\d{2}-\d{2}.*$/, "");
}

function dateOf(name: string): string | null {
  return /(\d{4}-\d{2}-\d{2})/.exec(name)?.[1] ?? null;
}

export default async function ReportsPage() {
  const [names, artifacts] = await Promise.all([listReports(), loadArtifacts()]);
  const byName = new Map(
    artifacts.map((a) => [a.file.replace("reports/", "").replace(/\.json$/, ""), a]),
  );
  const newestOfFamily = new Map<string, string>();
  for (const name of names) {
    const f = family(name);
    const current = newestOfFamily.get(f);
    if (!current || (dateOf(name) ?? "") > (dateOf(current) ?? "")) newestOfFamily.set(f, name);
  }
  return (
    <>
      <DocHeader eyebrow="وضعیت پروژه" title="گزارش‌های تولیدشده">
        هر عددی که در مستندات و صفحه‌ی اصلی می‌بینید از یکی از این گزارش‌ها می‌آید. هر گزارش را یک
        فرمان از پایگاه داده تولید کرده و فرمان، زمان تولید و داده‌ی پایه‌اش (match run، dataset
        hash، برچسب‌ها) همراهش است. گزارش‌های قدیمی‌تر پاک نمی‌شوند؛ به‌عنوان تاریخچه می‌مانند.
      </DocHeader>
      {names.length === 0 ? (
        <Callout kind="caution" title="پوشه‌ی reports خوانده نشد">
          متغیر <code className="ltr font-mono">REPORTS_DIR</code> را بررسی کنید.
        </Callout>
      ) : null}
      <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
        {names.map((name) => {
          const artifact = byName.get(name);
          const latest = newestOfFamily.get(family(name)) === name;
          return (
            <li key={name}>
              <Link
                href={`/docs/reports/${name}`}
                className="focus-ring flex flex-wrap items-center gap-x-4 gap-y-1 p-4 hover:bg-sunken"
              >
                <FileText aria-hidden="true" className="size-4 shrink-0 text-fg-muted" />
                <span className="font-medium text-fg">{reportName(`reports/${name}.md`)}</span>
                <span className="ltr font-mono text-xs text-fg-muted">{name}.md</span>
                <span className="ms-auto flex flex-wrap items-center gap-2">
                  {artifact ? <Badge tone="brand">داده‌ی ماشین‌خوان</Badge> : null}
                  {latest ? (
                    <Badge tone="verified">جدیدترین</Badge>
                  ) : (
                    <Badge tone="muted">تاریخچه</Badge>
                  )}
                  {artifact ? (
                    <span className="text-xs text-fg-muted">{faWhen(artifact.generated_at)}</span>
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
