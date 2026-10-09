import type { Metadata } from "next";

import { fetchClaimTask } from "@/lib/claim-labels";
import { apiBaseUrl } from "@/lib/health";
import { faNumber } from "@/lib/listing";

import { ClaimForm } from "./claim-form";

export const metadata: Metadata = {
  title: "برچسب ادعاهای توضیحات · ویلاسنج",
  robots: { index: false, follow: false },
};

type SearchParams = Record<string, string | string[] | undefined>;

export default async function ClaimLabelPage(props: { searchParams: Promise<SearchParams> }) {
  const params = await props.searchParams;
  const queue = typeof params.queue === "string" ? params.queue : "claims-v1";
  const labeler = typeof params.labeler === "string" ? params.labeler : "owner";
  const raw = typeof params.position === "string" ? Number.parseInt(params.position, 10) : NaN;
  const first = await fetchClaimTask(
    apiBaseUrl(),
    queue,
    labeler,
    Number.isNaN(raw) ? undefined : raw,
  );
  if (first.kind !== "ready") {
    return (
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-semibold text-balance">برچسب ادعاهای توضیحات</h1>
        <p className="mt-3 text-stone-600" role="alert">
          {first.kind === "missing"
            ? `صف «${queue}» هنوز ساخته نشده است.`
            : "بارگذاری ممکن نشد. API در دسترس است؟"}
        </p>
      </main>
    );
  }
  const task = first.task;
  return (
    <main className="mx-auto max-w-3xl px-4 pt-6 pb-16">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-semibold text-balance">برچسب ادعاهای توضیحات</h1>
        <p className="text-sm text-stone-600 tabular-nums">
          توضیح {faNumber(task.position)} از {faNumber(task.total)} · {faNumber(task.labelled)}{" "}
          برچسب‌خورده
        </p>
      </header>
      <p className="mt-2 text-sm text-pretty text-stone-600">
        فقط آنچه همین متن درباره‌ی خود ویلا می‌گوید را علامت بزنید؛ «مشاع» یعنی امکان مجموعه یا شهرک
        است، نه خود ویلا. خروجی قواعد ما این‌جا نشان داده نمی‌شود.
      </p>
      <h2 className="mt-5 font-medium text-balance">{task.title ?? "بدون عنوان"}</h2>
      <p className="mt-2 rounded-lg border border-stone-200 bg-white p-4 leading-8 whitespace-pre-line text-pretty">
        {task.description ?? "بدون توضیح"}
      </p>
      <ClaimForm
        key={`${task.platform}/${task.external_id}`}
        queue={queue}
        labeler={labeler}
        task={task}
      />
    </main>
  );
}
