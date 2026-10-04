/**
 * The project's own files the documentation shows as they are (ADRs, config): read at request time
 * from DOCS_DIR and CONFIG_DIR (the repository locally, read-only mounts in Docker), never copied.
 */
import "server-only";

import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

export function docsDir(): string {
  return process.env.DOCS_DIR ?? path.join(process.cwd(), "..", "docs");
}

export function configDir(): string {
  return process.env.CONFIG_DIR ?? path.join(process.cwd(), "..", "config");
}

export async function readConfig(name: string): Promise<string | null> {
  if (!/^[a-z0-9_-]+\.(toml|json)$/.test(name)) return null;
  try {
    return await readFile(path.join(configDir(), name), "utf8");
  } catch {
    return null;
  }
}

export type Adr = {
  slug: string; // 0014-er-decisions-rules-and-llm-judge
  number: string; // 0014
  title: string;
  status: string;
  amendments: { title: string }[];
  body: string;
};

function parseAdr(slug: string, text: string): Adr {
  const heading = /^#\s+ADR-(\d{4})\s+[—-]\s+(.+)$/m.exec(text);
  const status = /^Status:\s*(.+)$/m.exec(text);
  const amendments = [...text.matchAll(/^##\s+Amendment\s*(.*)$/gm)].map((m) => ({
    title: (m[1] ?? "").replace(/^\(|\)$/g, "").trim(),
  }));
  return {
    slug,
    number: heading?.[1] ?? slug.slice(0, 4),
    title: heading?.[2]?.trim() ?? slug,
    status: status?.[1]?.trim() ?? "",
    amendments,
    body: text,
  };
}

export async function loadAdrs(): Promise<Adr[]> {
  const dir = path.join(docsDir(), "adr");
  let names: string[];
  try {
    names = (await readdir(dir)).filter((n) => /^\d{4}-.+\.md$/.test(n)).sort();
  } catch {
    return [];
  }
  return Promise.all(
    names.map(async (n) =>
      parseAdr(n.replace(/\.md$/, ""), await readFile(path.join(dir, n), "utf8")),
    ),
  );
}

export async function loadAdr(slug: string): Promise<Adr | null> {
  if (!/^\d{4}-[a-z0-9-]+$/.test(slug)) return null;
  try {
    return parseAdr(slug, await readFile(path.join(docsDir(), "adr", `${slug}.md`), "utf8"));
  } catch {
    return null;
  }
}

export async function readReport(name: string): Promise<string | null> {
  if (!/^[a-z0-9.-]+$/.test(name)) return null;
  const { reportsDir } = await import("@/lib/artifacts");
  try {
    return await readFile(path.join(reportsDir(), `${name}.md`), "utf8");
  } catch {
    return null;
  }
}

export async function listReports(): Promise<string[]> {
  const { reportsDir } = await import("@/lib/artifacts");
  try {
    return (await readdir(reportsDir()))
      .filter((n) => n.endsWith(".md"))
      .map((n) => n.replace(/\.md$/, ""))
      .sort()
      .reverse();
  } catch {
    return [];
  }
}
