import { AskQuestion } from "@/components/ask-question";
import { ButtonLink } from "@/components/button";
import { Explorer } from "@/components/explorer";
import { Faq } from "@/components/faq";
import { Magnetic, Reveal } from "@/components/motion";
import { Eyebrow } from "@/components/ui";
import { getCourse, listCourses } from "@/lib/api/catalog";
import { summarize, type CourseSummary } from "@/lib/catalog";

export const revalidate = 60;

// Only what the product actually does today.
const QUESTIONS = [
  ["На каком языке курсы?", "На русском: уроки, задания и материалы."],
  [
    "Нужна дорогая техника?",
    "Нет. Что понадобится, написано на странице каждого курса. Часть курсов проходится со смартфоном.",
  ],
  [
    "Какие программы нужны?",
    "DaVinci Resolve бесплатен в базовой версии. Для курсов по Premiere Pro и After Effects нужна подписка Adobe, об этом сказано в требованиях курса.",
  ],
  [
    "Как оплатить?",
    "Картой местного банка через FreedomPay, на их защищённой странице. Данные карты к нам не попадают.",
  ],
  ["Доступ после покупки навсегда?", "Да. Купленный курс остаётся в аккаунте вместе с уроками и материалами."],
  [
    "Можно смотреть с телефона?",
    "Да, в браузере на телефоне или компьютере. Видео защищено, поэтому нужен обычный Chrome, Safari или Edge, не в режиме инкогнито.",
  ],
] as const;

async function loadCatalog(): Promise<CourseSummary[] | null> {
  try {
    const courses = await listCourses();
    // The list has no lesson counts; one detail call per course fills them in.
    const details = await Promise.all(courses.map((course) => getCourse(course.slug)));
    return courses.map((course, i) => summarize(course, details[i]));
  } catch (error) {
    console.error("catalog unavailable:", error);
    return null;
  }
}

export default async function Home() {
  const courses = await loadCatalog();

  return (
    <main>
      <Explorer courses={courses ?? []} unavailable={courses === null} />

      <section id="faq" className="py-[92px] max-md:py-[66px]">
        <div className="wrap">
          <Reveal className="mb-6">
            <Eyebrow className="mb-3">02 — Вопросы</Eyebrow>
            <h2 className="text-[clamp(26px,3.6vw,38px)] font-semibold leading-[1.1] tracking-[-0.038em]">Вопросы</h2>
          </Reveal>
          <Faq items={QUESTIONS} />
          <Reveal className="mt-8 flex flex-wrap items-center gap-4">
            <p className="text-[15px] text-muted">Не нашли ответ?</p>
            <AskQuestion variant="line" size="sm" />
          </Reveal>
        </div>
      </section>

      <section className="pb-[92px] pt-6">
        <div className="wrap">
          <Reveal className="relative isolate overflow-hidden rounded-[24px] border border-line bg-surface px-6 py-[clamp(38px,6vw,66px)] text-center">
            <div aria-hidden className="cta-glow" />
            <h2 className="text-[clamp(28px,4.8vw,48px)] font-semibold leading-[1.06] tracking-[-0.045em]">
              Начните с первого курса
            </h2>
            <p className="mx-auto mb-7 mt-4 max-w-[44ch] text-[16.5px] text-ink-2">
              Откройте программу, посмотрите, из чего состоит курс, и решайте. Доступ открывается сразу после оплаты.
            </p>
            <div className="flex flex-wrap justify-center gap-2.5">
              <Magnetic>
                <ButtonLink href="/#courses">Смотреть каталог</ButtonLink>
              </Magnetic>
              <AskQuestion variant="line" />
            </div>
          </Reveal>
        </div>
      </section>
    </main>
  );
}
