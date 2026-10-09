"use client";

import { Moon, Sun } from "lucide-react";

import { cn } from "@/lib/cn";
import { setTheme, useTheme } from "@/lib/theme";

/** One button: the icon shows the theme it switches to; the label says it in words. */
export function ThemeToggle({ className, en = false }: { className?: string; en?: boolean }) {
  const theme = useTheme();
  const dark = theme === "dark";
  const label = en
    ? dark
      ? "Switch to light theme"
      : "Switch to dark theme"
    : dark
      ? "پوسته‌ی روشن"
      : "پوسته‌ی تیره";
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={label}
      title={label}
      data-theme-toggle=""
      className={cn(
        "focus-ring grid size-10 shrink-0 place-items-center rounded-control text-fg-muted transition-colors hover:bg-sunken hover:text-fg active:scale-[0.96]",
        className,
      )}
    >
      {dark ? (
        <Sun aria-hidden="true" className="size-[1.125rem]" />
      ) : (
        <Moon aria-hidden="true" className="size-[1.125rem]" />
      )}
    </button>
  );
}
