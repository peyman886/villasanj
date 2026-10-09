"use client";

import { useSyncExternalStore } from "react";

/**
 * Light is the default; dark is the reader's choice, kept in localStorage and applied as
 * `data-theme` on <html> by THEME_SCRIPT before the first paint (no flash of the wrong theme).
 */
export type Theme = "light" | "dark";

export const THEME_KEY = "villasanj-theme";

/** «نسخه‌ی وب» on a phone: the page is laid out at this width, like a browser's desktop site. */
export const VIEW_KEY = "villasanj-view";
export const DESKTOP_WIDTH = 1280;
export const PHONE_SCREEN = 768; // a device narrower than this is a phone

/**
 * Runs in <head> before the body paints; it must not throw when storage is blocked. It applies
 * the saved theme and, on a phone whose reader chose the web version, widens the viewport. Next
 * streams its own viewport meta after this script, so every viewport meta, now and later, is set.
 */
export const THEME_SCRIPT = `try{var d=document.documentElement;if(localStorage.getItem("${THEME_KEY}")==="dark")d.dataset.theme="dark";if(localStorage.getItem("${VIEW_KEY}")==="desktop"&&screen.width<${PHONE_SCREEN}){d.dataset.view="desktop";var v="width=${DESKTOP_WIDTH}",w=function(){document.querySelectorAll('meta[name="viewport"]').forEach(function(m){if(m.getAttribute("content")!==v)m.setAttribute("content",v)})};w();new MutationObserver(w).observe(d,{childList:true,subtree:true})}}catch(e){}`;

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
