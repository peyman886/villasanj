import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/** A surface. `interactive` adds the hover elevation for cards that are links. */
export function Card({
  children,
  className,
  interactive = false,
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  as?: "div" | "article" | "section" | "li";
}) {
  return (
    <Tag
      className={cn(
        "rounded-card border border-line bg-surface shadow-raised",
        interactive && "transition-shadow duration-150 hover:shadow-float",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

/** A titled section of a page; the title is the landmark's accessible name. */
export function Section({
  id,
  title,
  eyebrow,
  description,
  action,
  children,
  className,
}: {
  id: string;
  title: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-labelledby={`${id}-title`} className={cn("scroll-mt-24", className)}>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="max-w-2xl">
          {eyebrow ? (
            <p className="text-xs font-semibold tracking-wide text-accent">{eyebrow}</p>
          ) : null}
          <h2 id={`${id}-title`} className="text-xl font-semibold text-balance text-fg">
            {title}
          </h2>
          {description ? (
            <p className="mt-1 text-sm text-pretty text-fg-muted">{description}</p>
          ) : null}
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}
