import { ArrowUpLeft, Bot, Lock, User, XCircle } from "lucide-react";
import Link from "next/link";

import { Heading } from "@/components/docs/prose";
import { Badge } from "@/components/ui/badge";
import { STATUS, StatusBadge } from "@/components/ui/status";
import {
  MILESTONES,
  OPEN_ITEMS,
  text,
  type Milestone,
  type OpenItem,
  type Status,
} from "@/content/milestones";
import { cn } from "@/lib/cn";
import { loadEvidence } from "@/lib/evidence";
import { faDate, faInt } from "@/lib/format";

const SEGMENT: Record<Status, string> = {
  done: "bg-brand-600",
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
    "partial",
    "provisional",
    "owner_review",
    "deferred",
    "blocked",
    "not_met",
  ];
  return order.map((s) => [s, all.filter((x) => x === s).length] as [Status, number]);
}

/** Every acceptance criterion as one stacked bar: how much is done, and what the rest is. */
export function CriteriaProgress() {
  const rows = counts();
  const total = rows.reduce((sum, [, n]) => sum + n, 0);
  const done = rows.find(([s]) => s === "done")?.[1] ?? 0;
  return (
    <figure className="rounded-card border border-line bg-surface p-5 shadow-raised">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold text-fg">معیارهای پذیرش M0 تا M11</span>
        <span className="text-sm text-fg-muted tabular-nums">
          {faInt(done)} از {faInt(total)} انجام شده
        </span>
      </figcaption>
      <div
        className="mt-3 flex h-3 overflow-hidden rounded-full bg-sunken"
        role="img"
        aria-label={rows
          .filter(([, n]) => n > 0)
          .map(([s, n]) => `${STATUS[s].text}: ${faInt(n)}`)
          .join("، ")}
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
              {STATUS[s].text} <span className="tabular-nums">{faInt(n)}</span>
            </li>
          ))}
      </ul>
    </figure>
  );
}

function tally(m: Milestone): string {
  const done = m.criteria.filter((c) => c.status === "done").length;
  return `${faInt(done)} از ${faInt(m.criteria.length)} معیار`;
}

/** M0–M11 as a compact grid of tiles, each linking to its checklist. */
export function MilestoneGrid() {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {MILESTONES.map((m) => (
        <li key={m.id}>
          <Link
            href={`/docs/milestones#${m.id.toLowerCase()}`}
            className="focus-ring group flex h-full flex-col gap-2 rounded-card border border-line bg-surface p-4 shadow-raised transition-shadow duration-150 hover:shadow-float"
          >
            <span className="flex items-center justify-between gap-2">
              <span className="ltr font-mono text-sm font-semibold text-accent">{m.id}</span>
              <StatusBadge status={m.status} />
            </span>
            <span className="font-semibold text-balance text-fg">{m.name_fa}</span>
            <span className="mt-auto text-xs text-fg-muted tabular-nums">{tally(m)}</span>
          </Link>
        </li>
      ))}
    </ol>
  );
}

/** The milestones in order, with what each delivered: the project's timeline. */
export function MilestoneTimeline() {
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
              <span className="font-semibold text-fg">{m.name_fa}</span>
              <StatusBadge status={m.status} />
              {m.date ? (
                <span className="text-xs text-fg-muted">{faDate(`${m.date}T12:00:00Z`)}</span>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-pretty text-fg-muted">{m.summary_fa}</p>
          </li>
        );
      })}
    </ol>
  );
}

/** Each milestone's criteria one by one, with the evidence read from the generated reports. */
export async function MilestoneChecklist() {
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
            {m.name_fa}
          </Heading>
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-fg-muted">
            <StatusBadge status={m.status} />
            <span className="tabular-nums">{tally(m)}</span>
            {m.date ? <span>· {faDate(`${m.date}T12:00:00Z`)}</span> : null}
            <span className="ltr text-xs text-fg-subtle">{m.name_en}</span>
          </div>
          <p className="mb-4 text-pretty text-fg">{m.summary_fa}</p>
          <ol className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface">
            {m.criteria.map((c) => (
              <li
                key={c.n}
                className="grid gap-x-4 gap-y-2 p-4 sm:grid-cols-[2rem_minmax(0,1fr)_auto]"
              >
                <span className="font-mono text-sm text-fg-subtle tabular-nums">{c.n}</span>
                <div className="min-w-0">
                  <p className="font-medium text-pretty text-fg">{c.title_fa}</p>
                  <p className="mt-1 text-sm text-pretty text-fg-muted">
                    {text(c.evidence_fa, evidence)}
                  </p>
                  {c.links?.length ? (
                    <p className="mt-1 flex flex-wrap gap-3 text-sm">
                      {c.links.map((l) => (
                        <Link
                          key={l.href}
                          href={l.href}
                          className="focus-ring inline-flex items-center gap-1 rounded-sm text-accent hover:underline"
                        >
                          {l.label}
                          <ArrowUpLeft aria-hidden="true" className="size-3.5" />
                        </Link>
                      ))}
                    </p>
                  ) : null}
                </div>
                <div className="sm:justify-self-end">
                  <StatusBadge status={c.status} />
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
  { title: string; Icon: typeof User; tone: "info" | "caution" | "danger" | "muted" }
> = {
  owner: { title: "به تصمیم یا بازبینی مالک نیاز دارد", Icon: User, tone: "info" },
  avalai: { title: "منتظر شارژ AvalAI", Icon: Bot, tone: "caution" },
  blocked: { title: "مسدود به دلیل بیرونی", Icon: Lock, tone: "muted" },
  not_met: { title: "پاس نشده", Icon: XCircle, tone: "danger" },
};

/** What is still open, grouped by what it waits for. */
export function OpenItems({ only }: { only?: OpenItem["kind"][] }) {
  const kinds = (only ?? (["not_met", "blocked", "avalai", "owner"] as const)).filter((k) =>
    OPEN_ITEMS.some((i) => i.kind === k),
  );
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {kinds.map((k) => {
        const K = KIND[k];
        return (
          <div key={k} className="rounded-card border border-line bg-surface p-4 shadow-raised">
            <p className="flex items-center gap-2 font-semibold text-fg">
              <K.Icon aria-hidden="true" className="size-4 text-fg-muted" />
              {K.title}
              <Badge tone={K.tone}>{faInt(OPEN_ITEMS.filter((i) => i.kind === k).length)}</Badge>
            </p>
            <ul className="mt-3 list-disc space-y-1.5 ps-5 text-sm text-pretty text-fg-muted marker:text-fg-subtle">
              {OPEN_ITEMS.filter((i) => i.kind === k).map((i) => (
                <li key={i.en}>{i.fa}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
