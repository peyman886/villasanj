import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "../globals.css";

import { BRAND } from "@/lib/copy";
import { THEME_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: { default: `${BRAND.name}: ${BRAND.tagline}`, template: `%s · ${BRAND.name}` },
  description: BRAND.description,
  applicationName: BRAND.name,
};

export const viewport: Viewport = {
  themeColor: [{ color: "#f9f8f6" }],
};

/** The Persian site's root (right to left). The English docs have their own root in (en). */
export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        {/* Applies the saved theme before the first paint (lib/theme.ts). */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-dvh bg-canvas font-sans text-fg antialiased">
        <a
          href="#main"
          className="focus-ring sr-only z-50 rounded-control bg-surface px-4 py-2 focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:shadow-float"
        >
          پرش به محتوا
        </a>
        {children}
      </body>
    </html>
  );
}
