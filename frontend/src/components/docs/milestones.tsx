import { ArrowUpLeft, ArrowUpRight, Bot, Lock, User, XCircle } from "lucide-react";
import Link from "next/link";

import { Heading } from "@/components/docs/prose";
import { Badge } from "@/components/ui/badge";
import { Callout } from "@/components/ui/callout";
import { STATUS, StatusBadge } from "@/components/ui/status";
import {
  MILESTONES,
  OPEN_ITEMS,
  text,
  type Milestone,
  type OpenItem,
  type Status,
} from "@/content/milestones";
import { docsPages } from "@/content/docs-nav";
import { cn } from "@/lib/cn";
import { loadEvidence } from "@/lib/evidence";
import { formatFor } from "@/lib/format";
import { docsHref, t, type Locale } from "@/lib/i18n";

const SEGMENT: Record<Status, string> = {
  done: "bg-brand-600",
  waived: "bg-sand-500",
  partial: "bg-sky-400",
  provisional: "bg-amber-400",
  blocked: "bg-rose-500",
  deferred: "bg-sand-400",
  owner_review: "bg-indigo-400",
  not_met: "bg-rose-700",
};

function counts(): [Status, number][] {
  const all = MILESTONES.flatMap((m) => m.criteria.map((c) => c.status));
  const order: Status[] = [
    "done",
    "waived",
    "partial",
    "provisional",
    "owner_review",
    "deferred",
    "blocked",
    "not_met",
  ];
  return order.map((s) => [s, all.filter((x) => x === s).length] as [Status, number]);
}

const statusText = (s: Status, locale: Locale) => (locale === "en" ? STATUS[s].en : STATUS[s].text);

/** Every acceptance criterion as one stacked bar: how much is done, and what the rest is. */
export function CriteriaProgress({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const rows = counts();
  const total = rows.reduce((sum, [, n]) => sum + n, 0);
  const done = rows.find(([s]) => s === "done")?.[1] ?? 0;
  const waived = rows.find(([s]) => s === "waived")?.[1] ?? 0;
  return (
    <figure className="rounded-card border border-line bg-surface p-5 shadow-raised">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold text-fg">
          {t(locale, "معیارهای پذیرش M0 تا M11", "Acceptance criteria, M0 to M11")}
        </span>
        <span className="text-sm text-fg-muted tabular-nums">
          {t(
            locale,
            `${f.int(done)} از ${f.int(total)} انجام شده`,
            `${f.int(done)} of ${f.int(total)} done`,
          )}
          {waived
            ? t(
                locale,
                ` · ${f.int(waived)} بسته به تصمیم مالک`,
                ` · ${f.int(waived)} closed by the owner`,
              )
            : ""}
        </span>
      </figcaption>
      <div
        className="mt-3 flex h-3 overflow-hidden rounded-full bg-sunken"
        role="img"
        aria-label={rows
          .filter(([, n]) => n > 0)
          .map(([s, n]) => `${statusText(s, locale)}: ${f.int(n)}`)
          .join(t(locale, "، ", ", "))}
      >
        {rows
          .filter(([, n]) => n > 0)
          .map(([s, n]) => (
            <span key={s} className={SEGMENT[s]} style={{ width: `${(n / total) * 100}%` }} />
          ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-fg-muted">
        {rows
          .filter(([, n]) => n > 0)
          .map(([s, n]) => (
            <li key={s} className="flex items-center gap-1.5">
              <span aria-hidden="true" className={cn("size-2.5 rounded-full", SEGMENT[s])} />
              {statusText(s, locale)} <span className="tabular-nums">{f.int(n)}</span>
            </li>
          ))}
      </ul>
    </figure>
  );
}

function tally(m: Milestone, locale: Locale): string {
  const f = formatFor(locale);
  const done = m.criteria.filter((c) => c.status === "done").length;
  const waived = m.criteria.filter((c) => c.status === "waived").length;
  if (locale === "en") {
    const closed = waived ? ` and ${f.int(waived)} closed by the owner` : "";
    const noun = m.criteria.length === 1 ? "criterion" : "criteria";
    return `${f.int(done)} done${closed} of ${f.int(m.criteria.length)} ${noun}`;
  }
  const closed = waived ? ` و ${f.int(waived)} بسته به تصمیم مالک` : "";
  return `${f.int(done)} انجام‌شده${closed} از ${f.int(m.criteria.length)} معیار`;
}

const nameOf = (m: Milestone, locale: Locale) => (locale === "en" ? m.name_en : m.name_fa);
const summaryOf = (m: Milestone, locale: Locale) => (locale === "en" ? m.summary_en : m.summary_fa);

/** A criterion's link in the reader's language (the label is the target page's title). */
function linkFor(l: { href: string; label: string }, locale: Locale) {
  const href = docsHref(l.href, locale);
  const label =
    locale === "en" ? (docsPages("en").find((p) => p.href === href)?.title ?? l.label) : l.label;
  return { href, label };
}

/** M0–M11 as a compact grid of tiles, each linking to its checklist. */
export function MilestoneGrid({ locale = "fa" }: { locale?: Locale }) {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {MILESTONES.map((m) => (
        <li key={m.id}>
          <Link
            href={docsHref(`/docs/milestones#${m.id.toLowerCase()}`, locale)}
            className="focus-ring group flex h-full flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-raised transition-shadow duration-150 hover:shadow-float"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="ltr font-mono text-sm font-semibold text-accent">{m.id}</span>
              <StatusBadge status={m.status} locale={locale} />
            </span>
            <span className="font-semibold text-balance text-fg">{nameOf(m, locale)}</span>
            <span className="mt-auto text-xs text-fg-muted tabular-nums">{tally(m, locale)}</span>
          </Link>
        </li>
      ))}
    </ol>
  );
}

/** The milestones in order, with what each delivered: the project's timeline. */
export function MilestoneTimeline({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  return (
    <ol className="relative ms-3 border-s-2 border-line">
      {MILESTONES.map((m) => {
        const s = STATUS[m.status];
        return (
          <li key={m.id} className="relative pb-6 ps-6 last:pb-0">
            <span
              aria-hidden="true"
              className={cn(
                "absolute -start-[0.6875rem] top-0.5 flex size-5 items-center justify-center rounded-full ring-4 ring-canvas",
                SEGMENT[m.status],
              )}
            >
              <s.Icon className="size-3 text-white" />
            </span>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="ltr font-mono text-sm font-semibold text-accent">{m.id}</span>
              <span className="font-semibold text-fg">{nameOf(m, locale)}</span>
              <StatusBadge status={m.status} locale={locale} />
              {m.date ? (
                <span className="text-xs text-fg-muted">{f.date(`${m.date}T12:00:00Z`)}</span>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-pretty text-fg-muted">{summaryOf(m, locale)}</p>
          </li>
        );
      })}
    </ol>
  );
}

/** Each milestone's criteria one by one, with the evidence read from the generated reports. */
export async function MilestoneChecklist({ locale = "fa" }: { locale?: Locale }) {
  const f = formatFor(locale);
  const en = locale === "en";
  const Arrow = en ? ArrowUpRight : ArrowUpLeft;
  const evidence = await loadEvidence();
  return (
    <div>
      {MILESTONES.map((m) => (
        <section key={m.id} aria-labelledby={m.id.toLowerCase()} className="scroll-mt-24">
          <Heading
            as="h2"
            id={m.id.toLowerCase()}
            className="first:mt-14 first:border-t first:pt-8"
          >
            <span className="ltr me-2 font-mono text-accent">{m.id}</span>
            {nameOf(m, locale)}
          </Heading>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            <StatusBadge status={m.status} locale={locale} />
            <span className="tabular-nums">{tally(m, locale)}</span>
            {m.date ? <span>· {f.date(`${m.date}T12:00:00Z`)}</span> : null}
            {en ? null : <span className="ltr text-xs text-fg-subtle">{m.name_en}</span>}
          </div>
          <p className="mb-4 text-pretty text-fg">{summaryOf(m, locale)}</p>
          <ol className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
            {m.criteria.map((c) => (
              <li
                key={c.n}
                className="grid gap-x-4 gap-y-2 p-4 sm:grid-cols-[2rem_minmax(0,1fr)_auto]"
              >
                <span className="font-mono text-sm text-fg-subtle tabular-nums">{c.n}</span>
                <div className="min-w-0">
                  <p className="font-medium text-pretty text-fg">{en ? c.title_en : c.title_fa}</p>
                  <p className="mt-1 text-sm text-pretty text-fg-muted">
                    {text(en ? c.evidence_en : c.evidence_fa, evidence)}
                  </p>
                  {c.links?.length ? (
                    <p className="mt-1 flex flex-wrap gap-3 text-sm">
                      {c.links.map((raw) => {
                        const l = linkFor(raw, locale);
                        return (
                          <Link
                            key={l.href}
                            href={l.href}
                            className="focus-ring inline-flex items-center gap-1 rounded-sm text-accent hover:underline"
                          >
                            {l.label}
                            <Arrow aria-hidden="true" className="size-3.5" />
                          </Link>
                        );
                      })}
                    </p>
                  ) : null}
                </div>
                <div className="sm:justify-self-end">
                  <StatusBadge status={c.status} locale={locale} />
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

const KIND: Record<
  OpenItem["kind"],
  { title: string; en: string; Icon: typeof User; tone: "info" | "caution" | "danger" | "muted" }
> = {
  owner: {
    title: "به تصمیم یا بازبینی مالک نیاز دارد",
    en: "Needs the owner's decision or review",
    Icon: User,
    tone: "info",
  },
  avalai: {
    title: "به فراخوانی AvalAI نیاز دارد",
    en: "Needs AvalAI calls",
    Icon: Bot,
    tone: "caution",
  },
  blocked: { title: "مسدود به دلیل بیرونی", en: "Blocked by others", Icon: Lock, tone: "muted" },
  not_met: { title: "پاس نشده", en: "Not met", Icon: XCircle, tone: "danger" },
};

/** What is still open, grouped by what it waits for. */
export function OpenItems({ only, locale = "fa" }: { only?: OpenItem["kind"][]; locale?: Locale }) {
  const f = formatFor(locale);
  const kinds = (only ?? (["not_met", "blocked", "avalai", "owner"] as const)).filter((k) =>
    OPEN_ITEMS.some((i) => i.kind === k),
  );
  if (kinds.length === 0) {
    return (
      <Callout kind="verified" title={t(locale, "هیچ کاری باز نیست", "Nothing is open")}>
        {t(
          locale,
          "همه‌ی معیارهای پذیرش M0 تا M11 یا انجام شده‌اند یا مالک صریحاً آن‌ها را بسته است.",
          "Every acceptance criterion of M0 to M11 is either done or explicitly closed by the owner.",
        )}
      </Callout>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {kinds.map((k) => {
        const K = KIND[k];
        return (
          <div key={k} className="rounded-card border border-line bg-surface p-4 shadow-raised">
            <p className="flex items-center gap-2 font-semibold text-fg">
              <K.Icon aria-hidden="true" className="size-4 text-fg-muted" />
              {locale === "en" ? K.en : K.title}
              <Badge tone={K.tone}>{f.int(OPEN_ITEMS.filter((i) => i.kind === k).length)}</Badge>
            </p>
            <ul className="mt-3 list-disc space-y-1.5 ps-5 text-sm text-pretty text-fg-muted marker:text-fg-subtle">
              {OPEN_ITEMS.filter((i) => i.kind === k).map((i) => (
                <li key={i.en}>{locale === "en" ? i.en : i.fa}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
