import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Project memory lives in the repo-root CLAUDE.md (AGENTS.md links to it); do not let
  // `next dev` add a second set of agent files under frontend/.
  agentRules: false,
};

export default nextConfig;
