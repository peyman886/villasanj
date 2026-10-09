"use client";

import { useSyncExternalStore } from "react";

/**
 * Light is the default; dark is the reader's choice, kept in localStorage and applied as
 * `data-theme` on <html> by THEME_SCRIPT before the first paint (no flash of the wrong theme).
 */
export type Theme = "light" | "dark";

export const THEME_KEY = "villasanj-theme";

/** Runs in <head> before the body paints; it must not throw when storage is blocked. */
export const THEME_SCRIPT = `try{if(localStorage.getItem("${THEME_KEY}")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}`;

export function currentTheme(): Theme {
  return typeof document !== "undefined" && document.documentElement.dataset.theme === "dark"
    ? "dark"
    : "light";
}

export function setTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "dark") root.dataset.theme = "dark";
  else delete root.dataset.theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Private windows may block storage: the choice then lasts for this page only.
  }
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

/** The page's theme, re-rendering when the toggle changes it (maps rebuild their style). */
export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, currentTheme, () => "light");
}
