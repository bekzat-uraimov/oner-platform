import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { buttonClass } from "@/components/button";
import { BuyButton } from "@/components/course/buy-button";
import { Curriculum } from "@/components/course/curriculum";
import { CourseArt } from "@/components/course-art";
import { ArrowIcon, CheckIcon, FileIcon, LockIcon } from "@/components/icons";
import { Enter, Reveal, RiseWords } from "@/components/motion";
import { Tilt } from "@/components/tilt";
import { getCourse } from "@/lib/api/catalog";
import { lessonsOf } from "@/lib/catalog";
import { FILES, formatLength, formatPrice, LESSONS, MODULES, plural } from "@/lib/format";

export const revalidate = 60;

export async function generateMetadata(props: PageProps<"/courses/[slug]">): Promise<Metadata> {
  const { slug } = await props.params;
  const course = await getCourse(slug);
  if (!course) return { title: "Курс не найден" };
  return { title: course.title, description: course.description ?? undefined };
}

/** "What you'll learn" and "Requirements" are free text, one item per line. */
function lines(text: string | null | undefined): string[] {
  return (text ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-[clamp(24px,3.2vw,34px)] font-semibold leading-[1.1] tracking-[-0.035em]">{children}</h2>;
}

function Chip({ children, accent = false }: { children: ReactNode; accent?: boolean }) {
  return (
    <span
      className={`rounded-full border px-3 py-1 text-[12.5px] font-medium ${
        accent ? "border-transparent bg-accent text-white" : "border-line bg-surface text-ink-2"
      }`}
    >
      {children}
    </span>
  );
}

export default async function CoursePage(props: PageProps<"/courses/[slug]">) {
  const { slug } = await props.params;
  const course = await getCourse(slug);
  if (!course) notFound();

  const lessons = lessonsOf(course);
  const seconds = lessons.reduce((sum, lesson) => sum + (lesson.duration ?? 0), 0);
  const outcomes = lines(course.learning_outcomes);
  const requirements = lines(course.requirements);
  const fileCount = course.materials.length + lessons.reduce((sum, lesson) => sum + (lesson.materials ?? []).length, 0);
  const price = formatPrice(course.price, course.currency);
  const facts = [
    `${lessons.length} ${plural(lessons.length, LESSONS)}`,
    `${course.modules.length} ${plural(course.modules.length, MODULES)}`,
    ...(seconds ? [formatLength(seconds)] : []),
  ];
  const included = [...facts, ...(fileCount ? [`${fileCount} ${plural(fileCount, FILES)}`] : []), "Доступ навсегда"];

  return (
    <main className="pb-24">
      <section className="hero-glow relative isolate pt-[136px] max-md:pt-[112px]">
        <div className="wrap grid items-center gap-12 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <Enter>
              <Link
                href="/#courses"
                className="group inline-flex items-center gap-2 text-sm font-medium text-muted transition-colors hover:text-ink"
              >
                <ArrowIcon className="size-3.5 rotate-180 transition-transform group-hover:-translate-x-0.5" />
                Каталог
              </Link>
            </Enter>
            <Enter delay={0.08} className="mt-7 flex flex-wrap gap-2">
              {course.segment && <Chip accent>{course.segment}</Chip>}
              {facts.map((fact) => (
                <Chip key={fact}>{fact}</Chip>
              ))}
            </Enter>
            <RiseWords
              text={course.title}
              delay={0.14}
              className="mt-5 max-w-[17ch] text-[clamp(34px,5.4vw,62px)] font-semibold leading-[1.04] tracking-[-0.045em]"
            />
            {course.description && (
              <Enter delay={0.32}>
                <p className="mt-5 max-w-[52ch] text-[clamp(16px,1.5vw,18px)] leading-[1.62] text-ink-2">
                  {course.description}
                </p>
              </Enter>
            )}
            <Enter delay={0.4} className="mt-8 flex flex-wrap items-center gap-3">
              <BuyButton courseId={course.id} slug={course.slug} label={`Купить за ${price}`} />
              <a href="#program" className={buttonClass("line")}>
                Программа
              </a>
            </Enter>
          </div>

          <Enter delay={0.2}>
            {/* Covers are 16:9 posters with their own labels, so they're shown whole, with nothing laid over them. */}
            <Tilt className="overflow-hidden rounded-[22px] border border-line shadow-float">
              <div className="relative aspect-video">
                <CourseArt title={course.title} cover={course.cover} segment={course.segment} className="absolute inset-0 h-full w-full" />
              </div>
            </Tilt>
          </Enter>
        </div>
      </section>

      <div className="wrap mt-[92px] grid gap-14 max-md:mt-16 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-[92px] max-md:gap-16">
          {outcomes.length > 0 && (
            <section>
              <Reveal>
                <SectionTitle>Чему научитесь</SectionTitle>
              </Reveal>
              <ul className="mt-7 grid gap-3 sm:grid-cols-2">
                {outcomes.map((item, i) => (
                  <Reveal
                    as="li"
                    key={item}
                    delay={Math.min(i * 0.06, 0.3)}
                    className="flex gap-3 rounded-card border border-line bg-surface p-5 text-[15px] leading-relaxed text-ink-2"
                  >
                    <span className="grid size-6 shrink-0 place-items-center rounded-full bg-ink text-bg">
                      <CheckIcon className="size-3" />
                    </span>
                    {item}
                  </Reveal>
                ))}
              </ul>
            </section>
          )}

          <section id="program">
            <Reveal className="flex flex-wrap items-end justify-between gap-4">
              <SectionTitle>Программа</SectionTitle>
              <span className="rounded-full border border-line px-[11px] py-[5px] font-mono text-[13px] text-muted">
                {facts.join(" · ")}
              </span>
            </Reveal>
            <Reveal delay={0.08} className="mt-7">
              {course.modules.length ? (
                <Curriculum modules={course.modules} />
              ) : (
                <p className="text-muted">Программа появится скоро.</p>
              )}
            </Reveal>
          </section>

          {requirements.length > 0 && (
            <section>
              <Reveal>
                <SectionTitle>Что понадобится</SectionTitle>
              </Reveal>
              <ul className="mt-6">
                {requirements.map((item, i) => (
                  <Reveal
                    as="li"
                    key={item}
                    delay={Math.min(i * 0.06, 0.3)}
                    className="flex items-center gap-3 border-b border-line py-4 text-[15px] text-ink-2 last:border-b-0"
                  >
                    <span className="size-1.5 shrink-0 rounded-full bg-accent" />
                    {item}
                  </Reveal>
                ))}
              </ul>
            </section>
          )}

          {course.materials.length > 0 && (
            <section>
              <Reveal>
                <SectionTitle>Материалы курса</SectionTitle>
                <p className="mt-2 text-[15px] text-muted">Скачиваются после покупки.</p>
              </Reveal>
              <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                {course.materials.map((file, i) => (
                  <Reveal
                    as="li"
                    key={file.id}
                    delay={Math.min(i * 0.06, 0.3)}
                    className="flex items-center gap-3 rounded-card border border-line p-4"
                  >
                    <span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-surface-2 text-ink-2">
                      <FileIcon className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1 truncate text-[15px] font-medium">{file.title}</span>
                    <span className="font-mono text-[11px] uppercase text-muted">{file.type}</span>
                    <LockIcon className="size-3.5 shrink-0 text-muted" />
                  </Reveal>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="max-lg:hidden">
          <Reveal className="sticky top-28 rounded-[18px] border border-line bg-bg p-6 shadow-lift">
            <p className="text-sm text-muted">Курс целиком</p>
            <p className="mt-2 text-[34px] font-semibold leading-none tracking-[-0.04em]">{price}</p>
            <ul className="mt-5 flex flex-col gap-2.5 text-sm text-ink-2">
              {included.map((item) => (
                <li key={item} className="flex items-center gap-2.5">
                  <CheckIcon className="size-3.5 text-green" />
                  {item}
                </li>
              ))}
            </ul>
            <BuyButton courseId={course.id} slug={course.slug} label="Купить курс" className="mt-6 w-full" />
            <p className="mt-3 text-center text-xs text-muted">Оплата картой через FreedomPay</p>
          </Reveal>
        </aside>
      </div>

      <div className="buy-bar fixed inset-x-3 bottom-3 z-50 flex items-center justify-between gap-3 rounded-full border border-line bg-bg/85 py-2 pl-5 pr-2 shadow-float backdrop-blur-xl lg:hidden">
        <span className="text-[15px] font-semibold tracking-[-0.02em]">{price}</span>
        <BuyButton courseId={course.id} slug={course.slug} label="Купить" size="sm" />
      </div>
    </main>
  );
}
