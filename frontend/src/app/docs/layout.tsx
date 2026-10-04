import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DocsMobileNav, DocsPager, DocsSidebar, DocsToc } from "@/components/docs/nav";
import { SiteFooter } from "@/components/site/footer";
import { SiteHeader } from "@/components/site/header";

export const metadata: Metadata = {
  title: { default: "مستندات پروژه", template: "%s · مستندات ویلاسنج" },
};

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <SiteHeader />
      <div className="mx-auto grid max-w-7xl gap-8 px-4 pt-8 sm:px-6 lg:grid-cols-[15rem_minmax(0,1fr)] xl:grid-cols-[15rem_minmax(0,1fr)_13rem]">
        <DocsSidebar />
        <main id="main" tabIndex={-1} className="min-w-0 outline-none">
          <DocsMobileNav />
          <article className="mt-6 lg:mt-0">{children}</article>
          <DocsPager />
        </main>
        <div className="hidden xl:block">
          <DocsToc />
        </div>
      </div>
      <SiteFooter />
    </>
  );
}
