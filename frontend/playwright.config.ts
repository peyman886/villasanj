import { defineConfig } from "@playwright/test";

/**
 * End-to-end checks against a running app with real data (ROADMAP M7 criteria 3 and 4).
 * Not part of `make test`: run `make test-e2e` with the web app and API up.
 *   E2E_BASE_URL  the web app (default http://localhost:3301, the host dev server)
 *   PW_CHANNEL    "chrome" uses the installed Google Chrome; empty uses Playwright's Chromium
 */
const channel = process.env.PW_CHANNEL ?? "chrome";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3301",
    locale: "fa-IR",
    ...(channel ? { channel } : {}),
  },
});
