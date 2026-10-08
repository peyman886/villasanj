import { FileText, Database } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { faDate } from "@/lib/format";

const REPORT_NAMES: [RegExp, string][] = [
  [/^er-eval-/, "ارزیابی تطبیق ویلاها"],
  [/^hypotheses-/, "گزارش فرضیه‌ها"],
  [/^h4-/, "گزارش H4"],
  [/^judge-eval-/, "ارزیابی داور"],
  [/^quality-/, "گزارش کیفیت و تست‌ها"],
  [/^performance-/, "گزارش کارایی"],
  [/^relevance-/, "ارزیابی مرتبط‌بودن جستجو"],
  [/^understanding-/, "ارزیابی فهم پرسش"],
];

/** A readable name for a generated report file. */
export function reportName(file: string): string {
  const base = file.replace("reports/", "");
  return REPORT_NAMES.find(([pattern]) => pattern.test(base))?.[1] ?? base;
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
}: {
  file?: string | undefined;
  generatedAt?: string | undefined;
  live?: boolean;
  label?: string;
  className?: string;
}) {
  const Icon = live ? Database : FileText;
  const text = live ? "زنده از پایگاه داده" : (label ?? (file ? reportName(file) : "منبع"));
  const body = (
    <>
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <span className="truncate">{text}</span>
      {generatedAt ? (
        <span className="shrink-0 text-fg-subtle">· {faDate(generatedAt)}</span>
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
        href={`/docs/reports/${encodeURIComponent(file.replace("reports/", "").replace(/\.json$/, ""))}`}
        className={cn(classes, "focus-ring hover:border-brand-300 hover:text-fg")}
        title={`${file} · ${generatedAt ?? ""}`}
      >
        {body}
      </Link>
    );
  }
  return <span className={classes}>{body}</span>;
}
