import { cn } from "@/lib/cn";
import { apiBaseUrl, fetchHealth, toHealthView, type HealthView } from "@/lib/health";

const checkedAtFormat = new Intl.DateTimeFormat("fa-IR", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: "Asia/Tehran",
});

const HEADLINE: Record<HealthView["kind"], string> = {
  ok: "همه‌ی اجزای سامانه سالم‌اند",
  degraded: "بخشی از سامانه در دسترس نیست",
  unreachable: "سرور API پاسخ نمی‌دهد",
};

export default async function HomePage() {
  const view = toHealthView(await fetchHealth(apiBaseUrl()));
  const checkedAt = checkedAtFormat.format(new Date());

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-10 px-6 py-16">
      <header className="flex flex-col gap-3">
        <p className="text-sm font-medium text-emerald-800">ترب برای ویلا</p>
        <h1 className="text-4xl font-bold text-balance">ویلاسنج</h1>
        <p className="text-xl text-stone-700 text-balance">یک ویلا، همه‌ی حقیقت</p>
        <p className="leading-8 text-stone-600 text-pretty">
          هر ویلای واقعی یک صفحه دارد: قیمت نهایی برای تاریخ و تعداد نفر شما، تقویم همه‌ی پلتفرم‌ها،
          نظرهای جمع‌شده و سنجش ادعاهای آگهی. هر عدد منبع و زمان مشاهده دارد.
        </p>
      </header>

      <section
        aria-labelledby="system-status"
        className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm"
      >
        <div className="flex flex-col gap-1">
          <h2 id="system-status" className="text-lg font-semibold text-balance">
            وضعیت سامانه
          </h2>
          <p
            className={cn("text-sm", view.kind === "ok" ? "text-emerald-800" : "text-amber-800")}
            role="status"
          >
            {HEADLINE[view.kind]}
          </p>
        </div>

        {view.kind === "unreachable" ? (
          <p className="mt-4 text-sm leading-7 text-stone-600 text-pretty">
            سرویس‌ها را با{" "}
            <code dir="ltr" className="rounded bg-stone-100 px-1.5 py-0.5">
              make up
            </code>{" "}
            اجرا کنید و خطاها را با{" "}
            <code dir="ltr" className="rounded bg-stone-100 px-1.5 py-0.5">
              make logs
            </code>{" "}
            ببینید.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-stone-100">
            {view.rows.map((row) => (
              <li key={row.key} className="flex items-center justify-between gap-4 py-3">
                <span>{row.label}</span>
                <span className="flex items-center gap-3">
                  <code dir="ltr" className="text-xs text-stone-500">
                    {row.detail}
                  </code>
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-0.5 text-xs font-medium",
                      row.ok ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-800",
                    )}
                  >
                    {row.ok ? "سالم" : "در دسترس نیست"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}

        <p className="mt-4 text-xs text-stone-500 tabular-nums">آخرین بررسی: {checkedAt}</p>
      </section>

      <footer className="text-xs text-stone-500">نسخه‌ی در حال ساخت</footer>
    </main>
  );
}
