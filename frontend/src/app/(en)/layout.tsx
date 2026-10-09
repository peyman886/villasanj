import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "../globals.css";

import { BRAND } from "@/lib/copy";
import { THEME_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: { default: `${BRAND.en.name}: ${BRAND.en.tagline}`, template: `%s · ${BRAND.en.name}` },
  description: BRAND.en.description,
  applicationName: BRAND.en.name,
};

export const viewport: Viewport = { themeColor: [{ color: "#f9f8f6" }] };

/** The English documentation's root (left to right); the product itself is Persian, in (fa). */
export default function EnglishRootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <head>
        {/* Applies the saved theme before the first paint (lib/theme.ts). */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-dvh bg-canvas font-sans text-fg antialiased">
        <a
          href="#main"
          className="focus-ring sr-only z-50 rounded-control bg-surface px-4 py-2 focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:shadow-float"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
