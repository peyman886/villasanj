// MapLibre 6 parses tiles in a module worker that imports "./maplibre-gl-shared.mjs"; Next does not
// serve files from node_modules, so both are copied next to each other under public/ before
// `next dev` and `next build` (always the installed version; the copies are git-ignored).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "node_modules", "maplibre-gl", "dist");
const target = join(root, "public", "maplibre");
mkdirSync(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(source, file), join(target, file));
}
