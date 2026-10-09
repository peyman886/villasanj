import type { Metadata } from "next";

import { apiBaseUrl } from "@/lib/health";
import { fetchPhotoTask } from "@/lib/photo-labels";

import { PhotoLabelingTool } from "./photo-labeling-tool";

export const metadata: Metadata = {
  title: "برچسب عکس‌ها · ویلاسنج",
  robots: { index: false, follow: false },
};

type SearchParams = Record<string, string | string[] | undefined>;

export default async function PhotoLabelPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const queue = typeof params.queue === "string" ? params.queue : "photos-v1";
  const labeler = typeof params.labeler === "string" ? params.labeler : "owner";
  const first = await fetchPhotoTask(apiBaseUrl(), queue, labeler);
  return <PhotoLabelingTool queue={queue} labeler={labeler} first={first} />;
}
