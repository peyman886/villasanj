import { ArrowUpLeft, FileCode2, Scale } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { loadAdrs } from "@/lib/project-files";

/** The top of every docs page: where it sits, what it is, and the one-paragraph answer. */
export function DocHeader({
  eyebrow,
  title,
  children,
  meta,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="mb-10 border-b border-line pb-8">
      <p className="text-sm font-semibold text-accent">{eyebrow}</p>
      <h1 className="mt-2 text-3xl font-bold text-balance text-fg sm:text-4xl">{title}</h1>
      {children ? (
        <div className="mt-4 max-w-3xl text-lg leading-8 text-pretty text-fg-muted [&_p]:my-0 [&_p+p]:mt-3">
          {children}
        </div>
      ) : null}
      {meta ? <div className="mt-5 flex flex-wrap items-center gap-2">{meta}</div> : null}
    </header>
  );
}

/** A link to an ADR by its number, with its title read from docs/adr. */
export async function Adr({ n, children }: { n: string; children?: ReactNode }) {
  const adr = (await loadAdrs()).find((a) => a.number === n);
  const href = adr ? `/docs/decisions/${adr.slug}` : "/docs/decisions";
  return (
    <Link
      href={href}
      title={adr?.title}
      className="focus-ring inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-0.5 align-middle text-xs font-medium text-fg-muted hover:border-brand-300 hover:text-fg"
    >
      <Scale aria-hidden="true" className="size-3.5" />
      <span className="ltr">ADR-{n}</span>
      {children ? <span>· {children}</span> : null}
    </Link>
  );
}

/** A source file in the repository, named left to right. */
export function SourceFile({ path }: { path: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-line bg-sunken px-2.5 py-0.5 align-middle text-xs text-fg-muted">
      <FileCode2 aria-hidden="true" className="size-3.5" />
      <span className="ltr font-mono">{path}</span>
    </span>
  );
}

/** A grid of small titled cards (contexts, principles, components). */
export function CardGrid({ children, cols = 2 }: { children: ReactNode; cols?: 2 | 3 }) {
  return (
    <div className={cn("my-6 grid gap-3 sm:grid-cols-2", cols === 3 && "lg:grid-cols-3")}>
      {children}
    </div>
  );
}

export function InfoCard({
  title,
  tag,
  href,
  children,
}: {
  title: string;
  tag?: string;
  href?: string;
  children: ReactNode;
}) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-fg">{title}</span>
        {tag ? <span className="ltr font-mono text-xs text-accent">{tag}</span> : null}
      </div>
      <div className="mt-1.5 text-sm leading-7 text-pretty text-fg-muted [&_p]:my-0 [&_p]:leading-7">
        {children}
      </div>
      {href ? (
        <span className="mt-2 inline-flex items-center gap-1 text-sm text-accent">
          بیشتر
          <ArrowUpLeft aria-hidden="true" className="size-3.5" />
        </span>
      ) : null}
    </>
  );
  const classes = "block h-full rounded-card border border-line bg-surface p-4 shadow-raised";
  return href ? (
    <Link
      href={href}
      className={cn(classes, "focus-ring transition-shadow duration-150 hover:shadow-float")}
    >
      {body}
    </Link>
  ) : (
    <div className={classes}>{body}</div>
  );
}

/** Numbered steps of a process, each with a title and a short explanation. */
export function Steps({ children }: { children: ReactNode }) {
  return <ol className="my-6 space-y-3 [counter-reset:step]">{children}</ol>;
}

export function Step({ title, children }: { title: string; children: ReactNode }) {
  return (
    <li className="relative rounded-card border border-line bg-surface p-4 ps-14 [counter-increment:step] before:absolute before:start-4 before:top-4 before:grid before:size-7 before:place-items-center before:rounded-full before:bg-brand-50 before:text-sm before:font-semibold before:text-brand-800 before:content-[counter(step,persian)]">
      <p className="font-semibold text-fg">{title}</p>
      <div className="mt-1 text-sm leading-7 text-pretty text-fg-muted [&_p]:my-0 [&_p]:leading-7 [&_p+p]:mt-2">
        {children}
      </div>
    </li>
  );
}
