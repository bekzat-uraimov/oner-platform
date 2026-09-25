const SUFFIX: Record<string, string> = { KGS: "с", KZT: "₸", UZS: "сум" };

const grouped = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });

/** "6990.00" in KGS → "6 990 с". The API sends prices as decimal strings; this only displays them. */
export function formatPrice(amount: string | number, currency: string): string {
  const n = grouped.format(Number(amount));
  return currency === "USD" ? `$${n}` : `${n} ${SUFFIX[currency] ?? currency}`;
}

/** Russian plurals: plural(5, LESSONS) → "уроков". */
export function plural(n: number, forms: readonly [string, string, string]): string {
  const a = n % 10;
  const b = n % 100;
  if (a === 1 && b !== 11) return forms[0];
  if (a >= 2 && a <= 4 && (b < 10 || b >= 20)) return forms[1];
  return forms[2];
}

export const LESSONS = ["урок", "урока", "уроков"] as const;
export const COURSES = ["курс", "курса", "курсов"] as const;
export const MODULES = ["модуль", "модуля", "модулей"] as const;
export const FILES = ["материал", "материала", "материалов"] as const;

/** 421 → "7:01", for one lesson. */
export function formatClock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/** 33600 → "9 ч 20 мин", for a whole course. */
export function formatLength(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  if (!h) return `${m} мин`;
  return m ? `${h} ч ${m} мин` : `${h} ч`;
}

export const pad = (n: number) => String(n).padStart(2, "0");

const dateTime = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** An API timestamp (UTC, with Z) in the viewer's own time zone. */
export function formatDate(value: string): string {
  return dateTime.format(new Date(value));
}

/** "7:01" → 421 seconds, "12" → 720 (minutes). Empty → null, anything else → NaN. */
export function parseClock(value: string): number | null {
  const text = value.trim();
  if (!text) return null;
  if (/^\d+$/.test(text)) return Number(text) * 60;
  const match = /^(\d+):([0-5]\d)$/.exec(text);
  return match ? Number(match[1]) * 60 + Number(match[2]) : Number.NaN;
}

const LATIN: Record<string, string> = {
  а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i", й: "y", к: "k",
  л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "ts",
  ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "", э: "e", ю: "yu", я: "ya", ө: "o", ү: "u", ң: "ng",
  ә: "a", қ: "k", ғ: "g", ұ: "u", һ: "h", і: "i",
};

/** A URL slug the API accepts: lowercase Latin, digits and single hyphens. Cyrillic is transliterated. */
export function slugify(text: string): string {
  return [...text.toLowerCase()]
    .map((ch) => LATIN[ch] ?? ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}
