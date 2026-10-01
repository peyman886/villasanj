import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "ویلاسنج",
  description: "یک ویلا، همه‌ی حقیقت: قیمت نهایی، تقویم و نظرهای همه‌ی پلتفرم‌ها در یک صفحه.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body className="min-h-dvh bg-stone-50 font-sans text-stone-900 antialiased">{children}</body>
    </html>
  );
}
