import { FileText, Database } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { formatFor } from "@/lib/format";
import { docsRoot, t, type Locale } from "@/lib/i18n";

const REPORT_NAMES: [RegExp, string, string][] = [
  [/^er-eval-/, "ارزیابی تطبیق ویلاها", "Entity resolution evaluation"],
  [/^hypotheses-/, "گزارش فرضیه‌ها", "Hypotheses report"],
  [/^h4-/, "گزارش H4", "H4 report"],
  [/^judge-eval-/, "ارزیابی داور", "Judge evaluation"],
  [/^quality-/, "گزارش کیفیت و تست‌ها", "Quality and test report"],
  [/^performance-/, "گزارش کارایی", "Performance report"],
  [/^relevance-/, "ارزیابی مرتبط‌بودن نتایج", "Search relevance evaluation"],
  [/^understanding-/, "ارزیابی فهم پرسش", "Query understanding evaluation"],
];

/** A readable name for a generated report file. */
export function reportName(file: string, locale: Locale = "fa"): string {
  const base = file.replace("reports/", "");
  const hit = REPORT_NAMES.find(([pattern]) => pattern.test(base));
  return hit ? (locale === "en" ? hit[2] : hit[1]) : base;
}

/**
 * Where a documented number comes from: a generated report (file, command, when) or the live
 * database. Every metric card and chart carries one.
 */
export function SourceChip({
  file,
  generatedAt,
  live = false,
  label,
  className,
  locale = "fa",
}: {
  file?: string | undefined;
  generatedAt?: string | undefined;
  live?: boolean;
  label?: string;
  className?: string;
  locale?: Locale;
}) {
  const Icon = live ? Database : FileText;
  const text = live
    ? t(locale, "زنده از پایگاه داده", "Live from the database")
    : (label ?? (file ? reportName(file, locale) : t(locale, "منبع", "Source")));
  const body = (
    <>
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="truncate">{text}</span>
      {generatedAt ? (
        <span className="shrink-0 text-fg-subtle">· {formatFor(locale).date(generatedAt)}</span>
      ) : null}
    </>
  );
  const classes = cn(
    "inline-flex max-w-full items-center gap-1.5 rounded-full border border-line bg-sunken px-2.5 py-0.5 text-xs text-fg-muted",
    className,
  );
  if (file && !live) {
    return (
      <Link
        href={`${docsRoot(locale)}/reports/${encodeURIComponent(file.replace("reports/", "").replace(/\.json$/, ""))}`}
        className={cn(classes, "focus-ring hover:border-brand-300 hover:text-fg")}
        title={`${file} · ${generatedAt ?? ""}`}
      >
        {body}
      </Link>
    );
  }
  return <span className={classes}>{body}</span>;
}
