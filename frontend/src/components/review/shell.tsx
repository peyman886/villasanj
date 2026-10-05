import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { LogoMark } from "@/components/site/logo";
import { ProgressBar } from "@/components/charts/bars";
import { faInt } from "@/lib/format";

/** The frame of a review tool: back to the hub, the task's title, and how far the queue is. */
export function ReviewShell({
  title,
  done,
  total,
  unit,
  children,
}: {
  title: string;
  done: number;
  total: number;
  unit: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-canvas">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <Link
            href="/review"
            className="focus-ring flex items-center gap-2 rounded-control text-sm text-fg-muted hover:text-fg"
          >
            <ArrowRight aria-hidden="true" className="size-4" />
            <LogoMark className="size-6" />
            همه‌ی بازبینی‌ها
          </Link>
          <h1 className="text-base font-semibold text-balance text-fg">{title}</h1>
          <div className="ms-auto w-full sm:w-64">
            <ProgressBar
              label="پیشرفت"
              value={done}
              max={Math.max(1, total)}
              display={`${faInt(done)} از ${faInt(total)} ${unit}`}
            />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 pt-6 pb-24">
        {children}
      </main>
    </div>
  );
}

export function ReviewUnavailable({
  title,
  missing,
  queue,
}: {
  title: string;
  missing: boolean;
  queue: string;
}) {
  return (
    <ReviewShell title={title} done={0} total={0} unit="">
      <p role="alert" className="rounded-card border border-line bg-surface p-5 text-fg-muted">
        {missing ? `صف «${queue}» هنوز ساخته نشده است.` : "بارگذاری ممکن نشد. API در دسترس است؟"}
      </p>
    </ReviewShell>
  );
}
