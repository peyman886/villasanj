import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DocsShell } from "@/components/docs/shell";
import { SiteFooter } from "@/components/site/footer";
import { SiteHeader } from "@/components/site/header";

export const metadata: Metadata = {
  title: { default: "مستندات", template: "%s · مستندات ویلاسنج" },
};

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <DocsShell header={<SiteHeader />} footer={<SiteFooter />}>
      {children}
    </DocsShell>
  );
}
