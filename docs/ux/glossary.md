# Glossary and style (Persian and English)

One term per idea in each language, used the same way in the product, the portal (`/docs` and
`/en/docs`), the README and the reports. When a term is missing here, pick the plainest one, use it
consistently, and add it.

## Name and message

| | Persian | English |
|---|---|---|
| Name | ویلاسنج | Villasanj |
| Tagline | قبل از رزرو، بسنجید | Compare before you book |
| One line | ویلاسنج آگهی‌های یک ویلا را در جاباما و شب پیدا می‌کند و قیمت، تقویم و نظرهایش را کنار هم نشان می‌دهد؛ هر عدد با منبعش. | Villasanj finds the same villa on Jabama and Shab and shows its prices, calendar and reviews side by side, every number with its source. |

The old line «یک ویلا، همه‌ی حقیقت» ("one villa, the whole truth") is retired everywhere.

## Terms

| Idea | Persian | English | Notes |
|---|---|---|---|
| a real villa (canonical) | ویلا | villa | never «ویلای کانونی» in prose |
| one platform's page for it | آگهی | listing | |
| rental site | پلتفرم | platform | jabama: جاباما / Jabama; shab: شب / Shab |
| matching listings to villas | تطبیق ویلاها | entity resolution (ER) | "matching" is fine in running text |
| checking a listing's claims | راستی‌آزمایی | truth check | not «حقیقت‌سنجی» |
| price of a stay on one platform | پیشنهاد، قیمت | offer, price | prices are never merged across listings |
| lower bound price | «از X» | "from X" | |
| where a number comes from | منبع و زمان مشاهده | provenance | |
| stored response | نسخه‌ی ذخیره‌شده (snapshot) | snapshot | first mention in Persian with the Latin word |
| fetching pages | خزش | crawling | «crawl» only in code and commands |
| night free on one platform only | شب پنهان | hidden night | |
| calendar of both platforms | تقویم یکپارچه | merged calendar | |
| LLM reviewer of pairs | داور مدل زبانی، داور | LLM judge, the judge | |
| labelled reference pairs | مجموعه‌ی طلایی (gold set) | gold set | |
| precision / recall | دقت / بازیابی | precision / recall | |
| 95% interval | بازه‌ی اطمینان ۹۵٪ | 95% confidence interval | |
| reading the query | فهم پرسش | query understanding | |
| ordering results | رتبه‌بندی | ranking | |
| acceptance criterion | معیار پذیرش | acceptance criterion | |
| architecture decision record | تصمیم معماری (ADR) | architecture decision record (ADR) | |
| project owner | مالک پروژه، مالک | the owner | |
| human labels | برچسب‌زنی، برچسب | labelling, labels | British spelling in English |
| LLM spend record | دفتر هزینه | cost ledger | |
| bounded context | زمینه‌ی مستقل (bounded context) | bounded context | |
| platform's approximate location | دایره‌ی موقعیت تقریبی | blur circle | |
| milestone | مایل‌استون | milestone | |
| search | جستجو | search | one word, as in the product («جستجو در همین محدوده») |

## Persian style

- Plain, short sentences, the way a careful Persian product writes. Prefer an active verb to a
  noun chain («ما بررسی می‌کنیم», not «انجام بررسی توسط ما»). No literal calques of English
  («در نظر گرفتن»، «در حال حاضر» when «الان» or «فعلاً» says it).
- Zero-width non-joiner where it belongs (می‌کند، ویلاها، خانه‌ی), Persian digits in prose, «»
  quotes, «؛» between clauses. No em dash or en dash; use «:» «؛» or a new sentence.
- Technical identifiers (file names, commands, model names) stay in Latin inside `code`. Common
  English engineering words appear in Latin only when a Persian engineer would say them that way
  (snapshot, pipeline); explain them once.
- Never accusatory: «تأیید نشد», never «دروغ» or «تقلب».

## English style

- British spelling (labelling, normalise, behaviour), sentence case headings, plain verbs, short
  paragraphs, written for a technical reviewer. No marketing adjectives.
- No em dash or en dash in prose (a hyphen in compound words is fine); use a colon, a semicolon or
  two sentences.
- Numbers come from the same artifacts as the Persian page. Never round differently, never add a
  number the Persian page does not have.
