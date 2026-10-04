import createMDX from "@next/mdx";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Project memory lives in the repo-root CLAUDE.md (AGENTS.md links to it); do not let
  // `next dev` add a second set of agent files under frontend/.
  agentRules: false,
  // The documentation portal's long-form pages are MDX (app/docs/**/page.mdx).
  pageExtensions: ["ts", "tsx", "md", "mdx"],
};

// Plugins are named as strings: Turbopack cannot receive JavaScript functions.
const withMDX = createMDX({
  options: {
    remarkPlugins: ["remark-gfm"],
    rehypePlugins: ["rehype-slug"],
  },
});

export default withMDX(nextConfig);
