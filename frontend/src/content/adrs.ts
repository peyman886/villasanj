/**
 * Persian and English titles and one-line summaries of the ADRs for the portal's cards. The ADR
 * text itself is read from docs/adr at request time and shown as written (English); a test checks
 * every ADR file has an entry here.
 */
export type AdrCard = {
  title_fa: string;
  summary_fa: string;
  area: string;
  title_en: string;
  summary_en: string;
  area_en: string;
};

export const ADR_CARDS: Record<string, AdrCard> = {
  "0001": {
    title_fa: "monolith ماژولار شش‌ضلعی با شش زمینه‌ی مستقل (bounded context)",
    summary_fa:
      "یک فرایند، مرزهای سخت: دامنه‌ی خالص، پورت‌ها در application، vendorها در infrastructure، و جهت وابستگی که import-linter اجبار می‌کند.",
    area: "معماری",
    title_en: "Hexagonal modular monolith with six bounded contexts",
    summary_en:
      "One process, hard boundaries: a pure domain, ports in the application layer, vendors in infrastructure, and a dependency direction that import-linter enforces.",
    area_en: "Architecture",
  },
  "0002": {
    title_fa: "پشته‌ی فناوری و آنچه عمداً کنار گذاشته شد",
    summary_fa:
      "Python 3.12 و FastAPI و SQLAlchemy، Next.js و TypeScript سخت‌گیر؛ بدون Redis، OpenSearch، Kafka یا framework تزریق وابستگی.",
    area: "معماری",
    title_en: "Technology stack, and what we deliberately left out",
    summary_en:
      "Python 3.12, FastAPI and SQLAlchemy; Next.js and strict TypeScript; no Redis, OpenSearch, Kafka or dependency-injection framework.",
    area_en: "Architecture",
  },
  "0003": {
    title_fa: "زیرساخت محلی روی Apple M4 با ۱۶ گیگابایت",
    summary_fa:
      "بودجه‌ی حافظه‌ی Docker، پروفایل‌های compose، OSRM روی برش منطقه، نقشه‌ی پایه‌ی آفلاین و نبود GPU در کانتینرها.",
    area: "زیرساخت",
    title_en: "Local infrastructure on a 16 GB Apple M4",
    summary_en:
      "The Docker memory budget, compose profiles, OSRM on a regional extract, an offline basemap and no GPU in containers.",
    area_en: "Infrastructure",
  },
  "0004": {
    title_fa: "دروازه‌ی مدل زبانی: AvalAI پشت LLMClient",
    summary_fa:
      "زنجیره‌ی مسیریابی، کش، تلاش دوباره، حاکم هزینه و اعتبارسنجی؛ dry-run با صفر فراخوانی و سقف سخت ۳۰ دلار.",
    area: "مدل زبانی",
    title_en: "LLM gateway: AvalAI behind LLMClient",
    summary_en:
      "A chain of routing, cache, retry, cost governor and validation; dry runs with zero calls and a hard cap of $30.",
    area_en: "Language models",
  },
  "0005": {
    title_fa: "مدل هر کار و برآورد هزینه",
    summary_fa:
      "انتخاب مدل با اندازه‌گیری: bake-offهای فهم پرسش، داور، توضیح، و تنظیم reasoning؛ اصلاحیه‌ها هر اندازه‌گیری را ثبت می‌کنند.",
    area: "مدل زبانی",
    title_en: "Model per task and cost estimate",
    summary_en:
      "Models chosen by measurement: bake-offs for query understanding, the judge and the explanation, and reasoning settings; amendments record each measurement.",
    area_en: "Language models",
  },
  "0006": {
    title_fa: "embeddingها: تصویر محلی، متن پشت دروازه‌ی ارزیابی",
    summary_fa:
      "بخش تصویر با ADR-0012 جایگزین شد؛ embedding متن تا وقتی ارزیابی بازیابی برتری‌اش را نشان ندهد ساخته نمی‌شود.",
    area: "مدل زبانی",
    title_en: "Embeddings: images local, text behind an evaluation gate",
    summary_en:
      "The image part was superseded by ADR-0012; text embeddings are not built until the retrieval evaluation shows they help.",
    area_en: "Language models",
  },
  "0007": {
    title_fa: "منبع برای هر عدد؛ مدل زبانی عدد نمی‌نویسد",
    summary_fa:
      "Sourced و Provenance در هسته‌ی مشترک، بازه به‌جای عدد ساختگی، اسلات و renderer و بررسی‌گر قطعی برای هر متن تولیدی.",
    area: "اعتماد",
    title_en: "Provenance for every number; LLMs never write numbers",
    summary_en:
      "Sourced and Provenance in the shared kernel, a range instead of an invented number, and slots, a renderer and a deterministic verifier for every generated text.",
    area_en: "Trust",
  },
  "0008": {
    title_fa: "خزش اخلاقی و تکرارپذیر",
    summary_fa:
      "بررسی robots.txt و شرایط استفاده پیش از اولین درخواست، یک درخواست هر ۳ ثانیه، توقف هنگام مسدودی، و snapshot از هر پاسخ.",
    area: "داده",
    title_en: "Ethical, reproducible crawling",
    summary_en:
      "A robots.txt and terms-of-service check before the first request, one request every 3 seconds, stop on block, and a snapshot of every response.",
    area_en: "Data",
  },
  "0009": {
    title_fa: "تطبیق مرحله‌ای با اولویت دقت",
    summary_fa:
      "blocking با اولویت بازیابی، شواهد با وزن فراوانی عکس، gold set برچسب انسان با بازه‌ی Wilson، و قاعده‌ی انتخاب نقطه‌ی کار.",
    area: "تطبیق",
    title_en: "Staged, precision-first entity resolution",
    summary_en:
      "Recall-first blocking, evidence weighted by photo frequency, a human-labelled gold set with Wilson intervals, and a rule for choosing the operating point.",
    area_en: "Entity resolution",
  },
  "0010": {
    title_fa: "یک Postgres: schema برای هر context، صف، کش و بردار",
    summary_fa:
      "PostGIS و pgvector در همان پایگاه داده؛ صف crawl با SKIP LOCKED؛ کش و دفتر هزینه‌ی مدل زبانی.",
    area: "زیرساخت",
    title_en: "One Postgres: a schema per context, queue, cache and vectors",
    summary_en:
      "PostGIS and pgvector in the same database; the crawl queue with SKIP LOCKED; the LLM cache and cost ledger.",
    area_en: "Infrastructure",
  },
  "0011": {
    title_fa: "دامنه‌ی پلتفرم‌ها پس از بررسی شرایط استفاده",
    summary_fa:
      "فقط جاباما و شب؛ جاجیگا، اتاقک و میهمانشو crawl را منع کرده‌اند و تا مجوز کتبی کنار می‌مانند.",
    area: "داده",
    title_en: "Platform scope after the terms-of-service audit",
    summary_en:
      "Jabama and Shab only; Jajiga, Otaghak and Mihmansho forbid crawling and stay out unless written permission arrives.",
    area_en: "Data",
  },
  "0012": {
    title_fa: "شاهد تصویری: DINOv2 محلی و pHash، با اندازه‌گیری",
    summary_fa:
      "benchmark روی داده‌ی خزش خودمان: DINOv2-small برش را تحمل می‌کند و ویلاهای نامرتبط را بهتر از embeddingهای API جدا نگه می‌دارد.",
    area: "تطبیق",
    title_en: "Image evidence: local DINOv2 and pHash, chosen by measurement",
    summary_en:
      "A benchmark on our own crawl: DINOv2-small tolerates crops and keeps unrelated villas apart better than the API embeddings.",
    area_en: "Entity resolution",
  },
  "0013": {
    title_fa: "شواهد جغرافیایی: خط ساحل OSM و زمان رانندگی OSRM",
    summary_fa:
      "snapshot باز OpenStreetMap، بازه روی موقعیت مبهم، مکان‌هایی که فقط تأیید می‌کنند، و زمان رانندگی بدون ترافیک.",
    area: "داده",
    title_en: "Geo evidence: OSM coastline and OSRM drive times",
    summary_en:
      "An open OpenStreetMap snapshot, a range for a blurred location, places that only confirm, and free-flow drive times.",
    area_en: "Data",
  },
  "0014": {
    title_fa: "تصمیم تطبیق: امتیاز قاعده‌ای، داور در یک بازه، برچسب مالک",
    summary_fa:
      "بدون Splink؛ داور مدل زبانی در بازه‌ی [۲−، ۳). پس از اصلاح برچسب‌ها: داور ادغام نادرست را رد می‌کند و ادغام تازه با انسان است.",
    area: "تطبیق",
    title_en: "Matching decisions: rule score, a judge in one zone, the owner's labels",
    summary_en:
      "No Splink; an LLM judge in the score zone [-2, 3). After the label revisions the judge vetoes wrong merges and a new merge needs a human.",
    area_en: "Entity resolution",
  },
  "0015": {
    title_fa: "نمایش عدم‌قطعیت در رابط کاربری",
    summary_fa:
      "«از» به‌جای «حداقل» با گرد کردن رو به پایین، بازه فقط وقتی باریک است «حدود»، هر هشدار یک بار در صفحه، سن مشاهده به‌جای «قدیمی»، و یک واژه‌نامه که آزمون‌ها بر آن نظارت می‌کنند.",
    area: "تجربه‌ی کاربری",
    title_en: "Presenting uncertainty in the UI",
    summary_en:
      "“From” instead of “at least”, rounded down; “about” only for a narrow range; each warning once per page; the observation's age instead of “old”; and one vocabulary that tests enforce.",
    area_en: "User experience",
  },
};
