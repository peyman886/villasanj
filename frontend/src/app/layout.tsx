import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ویلاسنج", template: "%s · ویلاسنج" },
  description: "یک ویلا، همه‌ی حقیقت: قیمت نهایی، تقویم و نظرهای همه‌ی پلتفرم‌ها در یک صفحه.",
};

export const viewport: Viewport = { themeColor: "#f9f8f6" };

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
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
