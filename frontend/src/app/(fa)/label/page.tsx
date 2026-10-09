import type { Metadata } from "next";

import { apiBaseUrl } from "@/lib/health";
import { fetchTask } from "@/lib/labeling";

import { LabelingTool } from "./labeling-tool";

export const metadata: Metadata = {
  title: "برچسب‌گذاری جفت آگهی‌ها · ویلاسنج",
  robots: { index: false, follow: false },
};

type SearchParams = Record<string, string | string[] | undefined>;

export default async function LabelPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const queue = typeof params.queue === "string" ? params.queue : "gold-v1";
  const labeler = typeof params.labeler === "string" ? params.labeler : "owner";
  const first = await fetchTask(apiBaseUrl(), queue, labeler);
  return <LabelingTool queue={queue} labeler={labeler} first={first} />;
}
