// Renders diagrams/*.mmd to static SVG (src/diagrams/generated.ts) and the English versions in
// diagrams/en/*.mmd to src/diagrams/generated-en.ts with a headless browser, so the documentation
// needs no diagram library or CDN at runtime and works in the offline demo.
// Usage: node scripts/render-diagrams.mjs        (render)
//        node scripts/render-diagrams.mjs --check (fail if a source changed since the last render)
import { createHash } from "node:crypto";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, "..");
const require = createRequire(import.meta.url);
// One set per language: the Persian portal (right to left) and the English one.
const SETS = [
  {
    dir: "rtl",
    sources: path.join(root, "diagrams"),
    out: path.join(root, "src", "diagrams", "generated.ts"),
    from: "diagrams/*.mmd",
  },
  {
    dir: "ltr",
    sources: path.join(root, "diagrams", "en"),
    out: path.join(root, "src", "diagrams", "generated-en.ts"),
    from: "diagrams/en/*.mmd",
  },
];

// Shared styles for flowcharts: one meaning per class, the same palette as the app.
const CLASSES = `
classDef default fill:#eef7f5,stroke:#3b8a83,stroke-width:1.2px,color:#25302e
classDef store fill:#eef2f8,stroke:#6f8db8,color:#1f2b3d
classDef llm fill:#fff4e2,stroke:#d29b3c,color:#3d2a08
classDef ext fill:#f4f1eb,stroke:#a89f8f,color:#2f2a22,stroke-dasharray:4 3
classDef human fill:#f1eefb,stroke:#8b78c9,color:#2a2342
classDef decision fill:#ffffff,stroke:#3b8a83,stroke-width:1.6px,color:#25302e
classDef good fill:#e3f3ee,stroke:#2f8a6c,color:#163a2e
classDef warn fill:#fdecec,stroke:#c46060,color:#4a1717
`;

const CONFIG = {
  startOnLoad: false,
  theme: "base",
  securityLevel: "strict",
  fontFamily: '"Vazirmatn Variable", "Vazirmatn", sans-serif',
  themeVariables: {
    fontFamily: '"Vazirmatn Variable", "Vazirmatn", sans-serif',
    fontSize: "14px",
    background: "#ffffff",
    primaryColor: "#eef7f5",
    primaryBorderColor: "#3b8a83",
    primaryTextColor: "#25302e",
    secondaryColor: "#f4f1eb",
    tertiaryColor: "#ffffff",
    lineColor: "#7b8784",
    textColor: "#25302e",
    clusterBkg: "#faf8f4",
    clusterBorder: "#d6cfc2",
    edgeLabelBackground: "#ffffff",
    actorBkg: "#eef7f5",
    actorBorder: "#3b8a83",
    actorTextColor: "#25302e",
    signalColor: "#5c6764",
    signalTextColor: "#25302e",
    noteBkgColor: "#fff7e0",
    noteBorderColor: "#d8b862",
    activationBkgColor: "#d6ece8",
    activationBorderColor: "#3b8a83",
  },
  flowchart: {
    htmlLabels: false,
    curve: "basis",
    padding: 14,
    nodeSpacing: 32,
    rankSpacing: 40,
    wrappingWidth: 280,
    useMaxWidth: true,
  },
  sequence: { useMaxWidth: true, mirrorActors: false, messageAlign: "center" },
};

function withClasses(source) {
  const first =
    source
      .trimStart()
      .split("\n")
      .find((l) => l.trim() && !l.trim().startsWith("%%")) ?? "";
  return /^(flowchart|graph)\b/.test(first.trim()) ? `${source.trimEnd()}\n${CLASSES}` : source;
}

function hashOf(source) {
  return createHash("sha256")
    .update(JSON.stringify(CONFIG))
    .update(CLASSES)
    .update(source)
    .digest("hex")
    .slice(0, 16);
}

async function sources(dir) {
  const names = (await readdir(dir).catch(() => [])).filter((n) => n.endsWith(".mmd")).sort();
  return Promise.all(
    names.map(async (n) => ({
      name: n.replace(/\.mmd$/, ""),
      source: await readFile(path.join(dir, n), "utf8"),
    })),
  );
}

async function check() {
  for (const set of SETS) {
    const generated = await readFile(set.out, "utf8").catch(() => "");
    const stale = (await sources(set.sources)).filter(
      ({ name, source }) => !generated.includes(`"${name}": {"hash":"${hashOf(source)}"`),
    );
    if (stale.length) {
      console.error(
        `stale diagrams in ${set.from} (run npm run diagrams): ${stale.map((s) => s.name).join(", ")}`,
      );
      process.exit(1);
    }
  }
  console.log("diagrams up to date");
}

async function render() {
  const { chromium } = require("playwright-core");
  const fontDir = path.join(root, "node_modules", "@fontsource-variable", "vazirmatn", "files");
  const font = async (file) => (await readFile(path.join(fontDir, file))).toString("base64");
  const [arabic, latin] = await Promise.all([
    font("vazirmatn-arabic-wght-normal.woff2"),
    font("vazirmatn-latin-wght-normal.woff2"),
  ]);
  const channel = process.env.PW_CHANNEL ?? "chrome"; // like the E2E suite: the installed Chrome
  const browser = await chromium.launch(channel ? { channel } : {});
  for (const set of SETS) await renderSet(browser, set, arabic, latin);
  await browser.close();
}

async function renderSet(browser, set, arabic, latin) {
  const page = await browser.newPage();
  await page.setContent(`<!doctype html><html dir="${set.dir}"><head><style>
    @font-face{font-family:"Vazirmatn Variable";font-weight:100 900;src:url(data:font/woff2;base64,${arabic}) format("woff2");unicode-range:U+0600-06FF,U+0750-077F,U+200C-200E,U+FB50-FDFF,U+FE70-FEFF}
    @font-face{font-family:"Vazirmatn Variable";font-weight:100 900;src:url(data:font/woff2;base64,${latin}) format("woff2")}
    body{font-family:"Vazirmatn Variable";margin:0}</style></head><body><div id="host"></div></body></html>`);
  // Load both ranges before Mermaid measures any text (an unused font is not loaded by itself).
  await page.evaluate(async () => {
    await document.fonts.load('600 14px "Vazirmatn Variable"', "سنجش ویلا");
    await document.fonts.load('400 14px "Vazirmatn Variable"', "Villasanj snapshot");
    await document.fonts.ready;
  });
  await page.addScriptTag({ path: require.resolve("mermaid/dist/mermaid.min.js") });
  await page.evaluate((config) => window.mermaid.initialize(config), CONFIG);
  const out = [];
  const styles = {};
  for (const { name, source } of await sources(set.sources)) {
    const svg = await page.evaluate(
      async ({ id, code }) => (await window.mermaid.render(id, code)).svg,
      { id: `diagram-${name}`, code: withClasses(source) },
    );
    out.push(
      `  "${name}": ${JSON.stringify({ hash: hashOf(source), ...slim(name, source, svg, styles) })},`,
    );
    console.log(`rendered ${set.from.replace("*", name)}`);
  }
  await page.close();
  await writeFile(
    set.out,
    `// Generated by scripts/render-diagrams.mjs from ${set.from}; do not edit by hand.\n` +
      `export type DiagramKind = "flow" | "seq";\n` +
      `export const DIAGRAM_STYLES: Record<DiagramKind, string> = ${JSON.stringify(styles)};\n` +
      `export const DIAGRAMS: Record<string, { hash: string; kind: DiagramKind; svg: string }> = {\n${out.join("\n")}\n};\n`,
  );
}

/**
 * Mermaid embeds the same theme stylesheet in every SVG, scoped to the diagram's id. It is moved out
 * once per kind (flowchart, sequence) and scoped to classes instead, and coordinates are rounded to
 * hundredths of a pixel: the same picture in a fraction of the bytes.
 */
function slim(name, source, svg, styles) {
  const kind = /^\s*sequenceDiagram/m.test(source) ? "seq" : "flow";
  const css = (/<style>([\s\S]*?)<\/style>/.exec(svg)?.[1] ?? "")
    .replaceAll(`url(#diagram-${name}-gradient)`, "url(#villasanj-diagram-gradient)")
    .replace(new RegExp(`#diagram-${name}(?![\\w-])`, "g"), `.villasanj-diagram.vd-${kind}`);
  if (styles[kind] !== undefined && styles[kind] !== css) {
    throw new Error(
      `diagram ${name}: its theme stylesheet differs from the other ${kind} diagrams`,
    );
  }
  styles[kind] = css;
  const open = svg.slice(0, svg.indexOf(">"));
  const classes = `villasanj-diagram vd-${kind}`;
  const body = (
    /\sclass="/.test(open)
      ? svg.replace(/(<svg[^>]*?\sclass=")/, `$1${classes} `)
      : svg.replace(/<svg /, `<svg class="${classes}" `)
  )
    .replace(/<style>[\s\S]*?<\/style>/, "")
    .replace(/(\d+\.\d{2})\d+/g, "$1");
  return { kind, svg: body };
}

await (process.argv.includes("--check") ? check() : render());
