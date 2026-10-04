import type { MDXComponents } from "mdx/types";

import { CodeBlock, Heading, InlineCode, ProseLink, ProseTable } from "@/components/docs/prose";

/** Markdown in the documentation portal rendered with the design system (required by @next/mdx). */
const components: MDXComponents = {
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
  p: ({ children }) => <p className="my-4 leading-8 text-pretty text-fg">{children}</p>,
  ul: ({ children }) => (
    <ul className="my-4 list-disc space-y-1.5 ps-6 leading-8 marker:text-brand-500">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-4 list-decimal space-y-1.5 ps-6 leading-8 marker:text-fg-muted">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="text-pretty">{children}</li>,
  a: ({ href, children }) => <ProseLink href={href}>{children}</ProseLink>,
  code: ({ children }) => <InlineCode>{children}</InlineCode>,
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  table: ({ children }) => <ProseTable>{children}</ProseTable>,
  blockquote: ({ children }) => (
    <blockquote className="my-5 rounded-card border-s-4 border-brand-400 bg-brand-50 px-5 py-1 text-brand-950">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-10 border-line" />,
  strong: ({ children }) => <strong className="font-semibold text-fg">{children}</strong>,
};

export function useMDXComponents(): MDXComponents {
  return components;
}
