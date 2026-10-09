import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { SectionAnchor, TableRegion } from "@/components/docs/prose-client";
import { cn } from "@/lib/cn";

/** Headings with a hover anchor; ids come from rehype-slug (MDX) or are given. */
export function Heading({
  as: Tag,
  id,
  children,
  className,
}: {
  as: "h2" | "h3" | "h4";
  id?: string | undefined;
  children: ReactNode;
  className?: string;
}) {
  const size = {
    h2: "mt-14 mb-4 border-t border-line pt-8 text-2xl font-bold first:mt-0 first:border-0 first:pt-0",
    h3: "mt-9 mb-3 text-lg font-semibold",
    h4: "mt-6 mb-2 font-semibold",
  }[Tag];
  return (
    <Tag id={id} className={cn("group scroll-mt-24 text-balance text-fg", size, className)}>
      {children}
      {id ? <SectionAnchor id={id} /> : null}
    </Tag>
  );
}

export function ProseLink({ href = "", children, ...rest }: ComponentProps<"a">) {
  const external = /^https?:/.test(href);
  const classes =
    "focus-ring rounded-sm text-accent underline decoration-brand-300 underline-offset-4 hover:decoration-brand-600";
  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={classes} {...rest}>
        {children}
      </a>
    );
  }
  return (
    <Link href={href} className={classes}>
      {children}
    </Link>
  );
}

/** Inline code: technical identifiers stay left-to-right inside Persian text. */
export function InlineCode({ children }: { children?: ReactNode }) {
  return (
    <code className="ltr rounded-md border border-line bg-sunken px-1.5 py-0.5 font-mono text-[0.85em] text-fg">
      {children}
    </code>
  );
}

/** A code or config block, always left-to-right, with an optional title. */
export function CodeBlock({ children, title }: { children?: ReactNode; title?: string }) {
  return (
    <figure className="my-5 overflow-hidden rounded-card border border-sand-800 bg-sand-950">
      {title ? (
        <figcaption
          className="border-b border-sand-800 px-4 py-2 font-mono text-xs text-sand-300"
          dir="ltr"
        >
          {title}
        </figcaption>
      ) : null}
      <pre
        dir="ltr"
        tabIndex={0}
        className="focus-ring overflow-x-auto p-4 text-start font-mono text-[13px] leading-6 text-sand-100 [&_code]:border-0 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-sand-100"
      >
        {children}
      </pre>
    </figure>
  );
}

export function ProseTable({ children }: { children?: ReactNode }) {
  return (
    <TableRegion>
      <table className="w-full min-w-[28rem] text-start text-sm tabular-nums [&_td]:px-3 [&_td]:py-2 [&_td]:align-top [&_th]:px-3 [&_th]:py-2 [&_th]:text-start [&_th]:font-medium [&_thead]:bg-sunken [&_thead]:text-fg-muted [&_tr]:border-t [&_tr]:border-line [&_thead_tr]:border-0">
        {children}
      </table>
    </TableRegion>
  );
}
