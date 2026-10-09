import type { Metadata } from "next";

import { ReportPage, reportMetadata } from "@/components/docs/pages/report";

type Props = { params: Promise<{ name: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return reportMetadata((await params).name, "en");
}

export default async function Page({ params }: Props) {
  return <ReportPage name={(await params).name} locale="en" />;
}
