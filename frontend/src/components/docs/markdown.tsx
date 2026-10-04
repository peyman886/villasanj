import type { ComponentProps } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

import { CodeBlock, Heading, InlineCode, ProseLink, ProseTable } from "@/components/docs/prose";

/**
 * Links inside the repository's markdown point at files (`0005-….md`, `../ROADMAP.md`). Inside the
 * portal they become portal routes; a file the portal does not show becomes plain text, so no page
 * ever links to something that 404s.
 */
export function portalHref(href: string): string | null {
  if (/^(https?:|mailto:)/.test(href)) return href;
  if (href.startsWith("#")) return href;
  const [file = "", anchor] = href.split("#");
  const base = file.split("/").pop() ?? "";
  const hash = anchor ? `#${anchor}` : "";
  const adr = /^(\d{4}-[a-z0-9-]+)\.md$/.exec(base);
  if (adr) return `/docs/decisions/${adr[1]}${hash}`;
  if (file.includes("reports/")) {
    const report = /^([a-z0-9.-]+)\.(md|json)$/.exec(base);
    if (report) return `/docs/reports/${report[1]}`;
  }
  const known: Record<string, string> = {
    "ARCHITECTURE.md": "/docs/architecture",
    "ROADMAP.md": "/docs/milestones",
    "README.md": file.includes("adr") ? "/docs/decisions" : "/docs",
    "demo-script.md": "/docs/demo",
    "er-labeling-protocol.md": "/docs/entity-resolution",
  };
  return known[base] ? `${known[base]}${hash}` : null;
}

const components: Components = {
  h1: ({ children }) => <h2 className="mb-4 text-2xl font-bold text-fg">{children}</h2>,
  h2: ({ id, children }) => (
    <Heading as="h2" id={id}>
      {children}
    </Heading>
  ),
  h3: ({ id, children }) => (
    <Heading as="h3" id={id}>
      {children}
    </Heading>
  ),
  h4: ({ id, children }) => (
    <Heading as="h4" id={id}>
      {children}
    </Heading>
  ),
  p: ({ children }) => <p className="my-4 leading-7 text-pretty text-fg">{children}</p>,
  ul: ({ children }) => (
    <ul className="my-4 list-disc space-y-1.5 ps-6 leading-7 marker:text-brand-500">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-4 list-decimal space-y-1.5 ps-6 leading-7 marker:text-fg-muted">
      {children}
    </ol>
  ),
  a: ({ href = "", children }) => {
    const to = portalHref(href);
    return to ? <ProseLink href={to}>{children}</ProseLink> : <span>{children}</span>;
  },
  code: ({ children, className }) =>
    className ? <code>{children}</code> : <InlineCode>{children}</InlineCode>,
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  table: ({ children }) => <ProseTable>{children}</ProseTable>,
  blockquote: ({ children }) => (
    <blockquote className="my-5 rounded-card border-s-4 border-brand-400 bg-brand-50 px-5 py-1 text-brand-950">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-8 border-line" />,
};

/** A repository markdown file (an ADR, a report) rendered with the design system. */
export function Markdown({
  children,
  ...rest
}: { children: string } & Omit<ComponentProps<"div">, "children">) {
  return (
    <div {...rest}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSlug]}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
