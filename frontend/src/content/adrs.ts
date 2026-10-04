/**
 * Persian titles and one-line summaries of the ADRs for the portal's cards. The ADR text itself is
 * read from docs/adr at request time and shown as written (English); a test checks every ADR file
 * has an entry here.
 */
export type AdrCard = { title_fa: string; summary_fa: string; area: string };

export const ADR_CARDS: Record<string, AdrCard> = {
  "0001": {
    title_fa: "monolith ماژولار شش‌ضلعی با شش bounded context",
    summary_fa:
      "یک فرایند، مرزهای سخت: دامنه‌ی خالص، پورت‌ها در application، vendorها در infrastructure، و جهت وابستگی که import-linter اجبار می‌کند.",
    area: "معماری",
  },
  "0002": {
    title_fa: "پشته‌ی فناوری و آنچه عمداً کنار گذاشته شد",
    summary_fa:
      "Python 3.12 و FastAPI و SQLAlchemy، Next.js و TypeScript سخت‌گیر؛ بدون Redis، OpenSearch، Kafka یا framework تزریق وابستگی.",
    area: "معماری",
  },
  "0003": {
    title_fa: "زیرساخت محلی روی Apple M4 با ۱۶ گیگابایت",
    summary_fa:
      "بودجه‌ی حافظه‌ی Docker، پروفایل‌های compose، OSRM روی برش منطقه، نقشه‌ی پایه‌ی آفلاین و نبود GPU در کانتینرها.",
    area: "زیرساخت",
  },
  "0004": {
    title_fa: "دروازه‌ی مدل زبانی: AvalAI پشت LLMClient",
    summary_fa:
      "زنجیره‌ی مسیریابی، کش، تلاش دوباره، حاکم هزینه و اعتبارسنجی؛ dry-run با صفر فراخوانی و سقف سخت ۳۰ دلار.",
    area: "مدل زبانی",
  },
  "0005": {
    title_fa: "مدل هر کار و برآورد هزینه",
    summary_fa:
      "انتخاب مدل با اندازه‌گیری: bake-offهای فهم پرسش، داور، توضیح، و تنظیم reasoning؛ اصلاحیه‌ها هر اندازه‌گیری را ثبت می‌کنند.",
    area: "مدل زبانی",
  },
  "0006": {
    title_fa: "embeddingها: تصویر محلی، متن پشت دروازه‌ی ارزیابی",
    summary_fa:
      "بخش تصویر با ADR-0012 جایگزین شد؛ embedding متن تا وقتی ارزیابی بازیابی برتری‌اش را نشان ندهد ساخته نمی‌شود.",
    area: "مدل زبانی",
  },
  "0007": {
    title_fa: "منبع برای هر عدد؛ مدل زبانی عدد نمی‌نویسد",
    summary_fa:
      "Sourced و Provenance در هسته‌ی مشترک، بازه به‌جای عدد ساختگی، اسلات و renderer و بررسی‌گر قطعی برای هر متن تولیدی.",
    area: "اعتماد",
  },
  "0008": {
    title_fa: "crawl اخلاقی و تکرارپذیر",
    summary_fa:
      "بررسی robots.txt و شرایط استفاده پیش از اولین درخواست، یک درخواست هر ۳ ثانیه، توقف هنگام مسدودی، و snapshot از هر پاسخ.",
    area: "داده",
  },
  "0009": {
    title_fa: "تطبیق مرحله‌ای با اولویت دقت",
    summary_fa:
      "blocking با اولویت بازیابی، شواهد با وزن فراوانی عکس، gold set برچسب انسان با بازه‌ی Wilson، و قاعده‌ی انتخاب نقطه‌ی کار.",
    area: "تطبیق",
  },
  "0010": {
    title_fa: "یک Postgres: schema برای هر context، صف، کش و بردار",
    summary_fa:
      "PostGIS و pgvector در همان پایگاه داده؛ صف crawl با SKIP LOCKED؛ کش و دفتر هزینه‌ی مدل زبانی.",
    area: "زیرساخت",
  },
  "0011": {
    title_fa: "دامنه‌ی پلتفرم‌ها پس از بررسی شرایط استفاده",
    summary_fa:
      "فقط جاباما و شب؛ جاجیگا، اتاقک و میهمانشو crawl را منع کرده‌اند و تا مجوز کتبی کنار می‌مانند.",
    area: "داده",
  },
  "0012": {
    title_fa: "شاهد تصویری: DINOv2 محلی و pHash، با اندازه‌گیری",
    summary_fa:
      "benchmark روی crawl خودمان: DINOv2-small برش را تحمل می‌کند و ویلاهای نامرتبط را بهتر از embeddingهای API جدا نگه می‌دارد.",
    area: "تطبیق",
  },
  "0013": {
    title_fa: "شواهد جغرافیایی: خط ساحل OSM و زمان رانندگی OSRM",
    summary_fa:
      "snapshot باز OpenStreetMap، بازه روی موقعیت مبهم، مکان‌هایی که فقط تأیید می‌کنند، و زمان رانندگی بدون ترافیک.",
    area: "داده",
  },
  "0014": {
    title_fa: "تصمیم تطبیق: امتیاز قاعده‌ای، داور در یک بازه، برچسب مالک",
    summary_fa:
      "بدون Splink؛ داور مدل‌زبانی در بازه‌ی [۲−، ۳). پس از اصلاح برچسب‌ها: داور ادغام نادرست را رد می‌کند و ادغام تازه با انسان است.",
    area: "تطبیق",
  },
};
