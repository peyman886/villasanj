import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DocsShell } from "@/components/docs/shell";
import { EnglishFooter, EnglishHeader } from "@/components/site/header-en";

export const metadata: Metadata = {
  title: { default: "Documentation", template: "%s · Villasanj docs" },
};

export default function EnglishDocsLayout({ children }: { children: ReactNode }) {
  return (
    <DocsShell header={<EnglishHeader />} footer={<EnglishFooter />}>
      {children}
    </DocsShell>
  );
}
