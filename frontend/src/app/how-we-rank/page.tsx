import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { faNumber } from "@/lib/listing";

export const metadata: Metadata = { title: "چطور رتبه‌بندی می‌کنیم · ویلاسنج" };

const FOCUS =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="mt-8">
      <h2 id={id} className="text-lg font-semibold text-balance">
        {title}
      </h2>
      <div className="mt-2 space-y-2 text-pretty text-stone-700">{children}</div>
    </section>
  );
}

function km(metres: number): string {
  return metres >= 1000 ? `${faNumber(metres / 1000)} کیلومتر` : `${faNumber(metres)} متر`;
}

export default async function HowWeRankPage() {
  let rules = null;
  try {
    const { data } = await apiClient().GET("/search/ranking", { cache: "no-store" });
    rules = data ?? null;
  } catch {
    rules = null;
  }
  const share = (name: string) => {
    const weight = rules?.weights[name];
    return weight === undefined ? "—" : `${faNumber(Math.round(weight * 100))}٪`;
  };
  const price = share("price");
  const rating = share("rating");
  return (
    <main className="mx-auto max-w-3xl px-4 pt-6 pb-16">
      <p className="text-sm text-stone-500">
        <Link href="/" className={cn("underline-offset-4 hover:underline", FOCUS)}>
          ویلاسنج
        </Link>
      </p>
      <h1 className="mt-1 text-2xl font-semibold text-balance">چطور رتبه‌بندی می‌کنیم</h1>
      <p className="mt-2 text-pretty text-stone-600">
        هیچ پلتفرمی برای جایگاه بالاتر به ما پول نمی‌دهد و در رتبه‌بندی هیچ ضریب کمیسیون یا تبلیغی
        نیست. هر چه این‌جا می‌بینید از کدی می‌آید که نتیجه‌ها را می‌سازد.
      </p>

      <Section id="excluded" title="چه چیزی کنار گذاشته می‌شود">
        <p>
          فقط واقعیت‌های گفته‌شده: شبی که در آخرین مشاهده آزاد نبود، ظرفیتی کمتر از گروه شما، اتاق
          خواب کمتر از خواسته، حداقل قیمتی بالاتر از بودجه، امکانی که خود آگهی گفته ندارد، و زمان
          رانندگی‌ای که حتی در بهترین حالت از سقف شما بیشتر است. دلیل هر کنار گذاشتن شمرده و نشان
          داده می‌شود.
        </p>
        <p>
          چیزی که معلوم نیست (ظرفیت منتشرنشده، هزینه‌های جانبی، امکانی که کسی تأیید نکرده) آگهی را
          حذف نمی‌کند؛ با یک هشدار می‌ماند و امتیازی هم نمی‌گیرد.
        </p>
      </Section>

      <Section id="order" title="ترتیب نتیجه‌ها">
        <p>
          اول آگهی‌هایی که امکانات خواسته‌شده‌شان تأیید شده، بعد بقیه. در هر گروه، امتیاز جمع دو بخش
          نام‌دار است: قیمت برای هر نفر در هر شب ({price}؛ ارزان‌تر بیشتر، نسبت به همین جست‌وجو) و
          امتیاز مهمان‌ها ({rating}؛ با میانگین پلتفرم تعدیل می‌شود تا دو رأی پنج‌ستاره هم‌وزن صد
          رأی نباشد). سهم هر بخش روی هر نتیجه نشان داده می‌شود.
        </p>
      </Section>

      <Section id="prices" title="قیمت‌ها">
        <p>
          قیمت هر نتیجه جمع کل اقامت برای همان تاریخ و همان تعداد نفر است، از شب‌هایی که در صفحه‌ی
          پلتفرم دیده‌ایم. هیچ پلتفرمی کارمزدش را منتشر نمی‌کند، پس قیمت‌ها «حداقل» هستند و هرگز
          سقفی از خودمان نمی‌سازیم. قیمت دو پلتفرم با هم ترکیب نمی‌شود و هر عدد منبع و زمان
          مشاهده‌اش را دارد.
        </p>
      </Section>

      <Section id="truth" title="حقیقت‌سنجی ادعاها">
        <p>
          «تأیید شد» یعنی شاهد مستقل (نقشه) با ادعا جور است. «تأیید نشد» یعنی شاهد کافی نداریم، نه
          اینکه ادعا نادرست است. «با نقشه نمی‌خواند» فقط وقتی گفته می‌شود که حتی سخاوتمندانه‌ترین
          برداشت از ادعا و نزدیک‌ترین جای ممکن ویلا به هم نرسند.
        </p>
        <p>
          فاصله‌ها از نقشه‌ی OpenStreetMap و در خط مستقیم حساب می‌شوند. پلتفرم‌ها جای دقیق ویلا را
          نمی‌گویند، پس هر فاصله یک بازه است روی دایره‌ی اطراف نقطه‌ی منتشرشده
          {rules ? ` (اگر شعاع منتشر نشده باشد ${km(rules.unknown_radius_m)} فرض می‌شود)` : ""}.
          نقشه همه‌ی سوپرمارکت‌ها، نانوایی‌ها و رستوران‌ها را ندارد، پس آن‌ها فقط تأیید می‌کنند و
          هرگز رد نمی‌کنند. مرکز شهر یک محدوده است
          {rules ? `، تا ${km(rules.centre_extent_m)} دورتر از نقطه‌ی مرکز` : ""}.
          {rules ? ` «نزدیک دریا» یعنی تا ${km(rules.near_sea_m)} تا ساحل در خط مستقیم.` : ""}
        </p>
      </Section>

      <Section id="drive" title="زمان رانندگی">
        <p>
          زمان رانندگی بدون ترافیک
          {rules?.origin ? ` از ${rules.origin}` : ""} و روی همان نقشه حساب می‌شود؛ در تعطیلات شلوغ
          بیشتر طول می‌کشد. چون جای دقیق ویلا معلوم نیست، این هم یک بازه است.
        </p>
      </Section>

      <Section id="why" title="توضیح «چرا گزینه‌ی اول؟»">
        <p>
          مدل زبانی فقط جمله‌ها را می‌نویسد. هر عدد، تاریخ و مقایسه را کد از داده‌ها می‌سازد و پیش
          از نمایش بررسی می‌شود؛ اگر متن مدل از بررسی رد شود، یک قالب ثابت جای آن می‌نشیند.
        </p>
      </Section>
    </main>
  );
}
