import type { Metadata } from "next";

import { DecisionPage, decisionMetadata } from "@/components/docs/pages/decision";

type Props = { params: Promise<{ slug: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return decisionMetadata((await params).slug, "en");
}

export default async function Page({ params }: Props) {
  return <DecisionPage slug={(await params).slug} locale="en" />;
}
