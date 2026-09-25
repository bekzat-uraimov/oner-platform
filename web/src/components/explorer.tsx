"use client";

import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { CourseCard } from "./course-card";
import { SearchIcon, YouTubeIcon } from "./icons";
import { CountUp, Enter, Reveal, RiseWords } from "./motion";
import { ToolLogos } from "./tool-logos";
import { Eyebrow } from "./ui";
import type { CourseSummary } from "@/lib/catalog";
import { COURSES, LESSONS, plural } from "@/lib/format";
import { EASE } from "@/lib/motion";
import { YOUTUBE_URL } from "@/lib/site";

const ALL = "all";
const PLACEHOLDER = "Чему хотите научиться?";

/** The hero and the catalog, which share one search box. */
export function Explorer({ courses, unavailable }: { courses: CourseSummary[]; unavailable: boolean }) {
  const [query, setQuery] = useState("");
  const [segment, setSegment] = useState(ALL);
  const reduce = useReducedMotion();

  const segments = useMemo(
    () => [...new Set(courses.map((c) => c.segment).filter((s): s is string => Boolean(s)))],
    [courses],
  );
  // "Цветокоррекция в DaVinci Resolve" → "цветокоррекция в DaVinci Resolve", so brand names keep their case.
  const titles = useMemo(
    () => courses.map((c) => (/^.\p{Ll}/u.test(c.title) ? c.title[0].toLowerCase() + c.title.slice(1) : c.title)),
    [courses],
  );
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return courses.filter(
      (c) =>
        (segment === ALL || c.segment === segment) &&
        (!q || `${c.title} ${c.description ?? ""} ${c.segment ?? ""}`.toLowerCase().includes(q)),
    );
  }, [courses, segment, query]);
  const lessons = courses.reduce((sum, c) => sum + c.lessons, 0);

  function jumpToCatalog() {
    document.getElementById("courses")?.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
  }

  return (
    <>
      <header className="hero-glow relative isolate pb-[52px] pt-[164px] text-center max-md:pb-11 max-md:pt-[126px]">
        <div className="wrap">
          <Enter delay={0.06}>
            <span className="inline-flex items-center gap-[10px] rounded-full border border-line bg-surface py-1.5 pl-[10px] pr-4 font-mono text-[11px] uppercase tracking-[0.2em] text-ink-2">
              <i className="relative block size-[7px] rounded-full bg-brand">
                <i className="absolute inset-0 animate-ping rounded-full bg-brand opacity-60" />
              </i>
              Искусство · ремесло · мастерство
            </span>
          </Enter>
          <RiseWords
            text="Учись у лучших"
            accent="."
            className="mx-auto mt-7 text-[clamp(52px,9.4vw,120px)] font-semibold leading-[0.95] tracking-[-0.055em]"
          />
          <Enter delay={0.26}>
            <p className="mx-auto mt-6 max-w-[52ch] text-[clamp(16px,1.6vw,18.5px)] leading-[1.62] text-ink-2">
              Видеокурсы по съёмке, свету, монтажу, цвету и режиссуре от признанных профессионалов Центральной Азии.
            </p>
          </Enter>
          <Enter delay={0.3}>
            <SearchPill value={query} onChange={setQuery} onSubmit={jumpToCatalog} words={titles} />
          </Enter>
          <Enter delay={0.38} className="mt-5 flex flex-wrap items-center justify-center gap-x-4 gap-y-3 text-[13px] text-muted">
            {courses.length > 0 && (
              <span>
                <CountUp to={courses.length} /> {plural(courses.length, COURSES)} · <CountUp to={lessons} />{" "}
                {plural(lessons, LESSONS)} · оплата местной картой
              </span>
            )}
            <a
              href={YOUTUBE_URL}
              target="_blank"
              rel="noreferrer"
              className="group inline-flex items-center gap-2 rounded-full border border-line bg-bg py-1.5 pl-2 pr-3.5 font-medium text-ink-2 shadow-soft transition-[border-color,color,box-shadow] duration-300 hover:border-line-strong hover:text-ink hover:shadow-lift"
            >
              <YouTubeIcon className="size-5 transition-transform duration-300 group-hover:scale-110" />
              Смотреть нас на YouTube
            </a>
          </Enter>
          <Enter delay={0.46}>
            <ToolLogos />
          </Enter>
        </div>
      </header>

      <section id="courses" className="py-[92px] max-md:py-[66px]">
        <div className="wrap">
          <Reveal className="mb-8 flex flex-wrap items-end justify-between gap-6">
            <div>
              <Eyebrow className="mb-3">01 — Каталог</Eyebrow>
              <h2 className="text-[clamp(26px,3.6vw,38px)] font-semibold leading-[1.1] tracking-[-0.038em]">Каталог</h2>
              <p className="mt-[9px] max-w-[50ch] text-[15px] text-muted">
                Каждый курс ведёт практик, который снимает, монтирует и красит проекты прямо сейчас.
              </p>
            </div>
            <span className="rounded-full border border-line px-[11px] py-[5px] font-mono text-[13px] text-muted">
              {shown.length} {plural(shown.length, COURSES)}
            </span>
          </Reveal>

          {segments.length > 1 && (
            <Reveal delay={0.07}>
              <SegmentTabs options={segments} value={segment} onChange={setSegment} />
            </Reveal>
          )}

          {unavailable ? (
            <p className="py-[60px] text-center text-[15px] text-muted">
              Каталог временно недоступен. Обновите страницу через минуту.
            </p>
          ) : (
            <>
              <motion.div layout className="grid grid-cols-[repeat(auto-fill,minmax(min(320px,100%),1fr))] gap-[22px]">
                <AnimatePresence mode="popLayout">
                  {shown.map((course, i) => (
                    <motion.div
                      key={course.slug}
                      layout
                      initial={{ opacity: 0, y: 22, scale: 0.97, filter: "blur(7px)" }}
                      whileInView={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
                      // Leaving cards go at once; the entrance stagger would make filtering feel slow.
                      exit={{ opacity: 0, scale: 0.94, filter: "blur(4px)", transition: { duration: 0.28, ease: EASE } }}
                      viewport={{ once: true, margin: "0px 0px -40px 0px" }}
                      transition={{
                        default: { duration: 0.7, ease: EASE, delay: Math.min(i * 0.07, 0.26) },
                        layout: { duration: 0.54, ease: EASE },
                      }}
                    >
                      <CourseCard course={course} />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </motion.div>
              <AnimatePresence>
                {shown.length === 0 && (
                  <motion.p
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.4, ease: EASE }}
                    className="py-[60px] text-center text-[15px] text-muted"
                  >
                    Ничего не нашлось. Попробуйте другое слово.
                  </motion.p>
                )}
              </AnimatePresence>
            </>
          )}
        </div>
      </section>
    </>
  );
}

function SegmentTabs({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <LayoutGroup id="segments">
      <div role="tablist" aria-label="Категории" className="mb-[26px] flex flex-wrap gap-1.5">
        {[ALL, ...options].map((option) => {
          const selected = option === value;
          return (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(option)}
              className={`relative rounded-full border px-[15px] py-2 text-sm font-medium transition-colors duration-300 ${
                selected ? "border-transparent text-bg" : "border-line text-ink-2 hover:bg-surface-2"
              }`}
            >
              {selected && (
                <motion.span
                  layoutId="segment-pill"
                  className="absolute -inset-px rounded-full bg-ink"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <span className="relative">{option === ALL ? "Все" : option}</span>
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
}

function SearchPill({
  value,
  onChange,
  onSubmit,
  words,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  words: string[];
}) {
  const input = useRef<HTMLInputElement>(null);
  const reduce = useReducedMotion();

  // Types real course titles into the placeholder, then erases them. Writes the
  // DOM directly: a re-render every 60ms would be wasted work.
  useEffect(() => {
    const el = input.current;
    if (!el || reduce || words.length === 0) return;
    const base = `${PLACEHOLDER} Например, `;
    let word = 0;
    let chars = 0;
    let dir = 1;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      if (document.activeElement === el || el.value) {
        timer = setTimeout(tick, 1200);
        return;
      }
      const target = words[word];
      chars += dir;
      el.placeholder = base + target.slice(0, chars);
      let wait = dir === 1 ? 60 : 26;
      if (dir === 1 && chars >= target.length) {
        dir = -1;
        wait = 1700;
      } else if (dir === -1 && chars <= 0) {
        dir = 1;
        word = (word + 1) % words.length;
        wait = 260;
      }
      timer = setTimeout(tick, wait);
    };

    timer = setTimeout(tick, 1400);
    return () => {
      clearTimeout(timer);
      el.placeholder = PLACEHOLDER;
    };
  }, [reduce, words]);

  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="mx-auto mt-8 flex max-w-[540px] items-center gap-[11px] rounded-full border border-line bg-bg py-1.5 pl-[18px] pr-1.5 shadow-soft transition-[border-color,box-shadow] duration-300 focus-within:border-line-strong focus-within:shadow-lift"
    >
      <SearchIcon className="size-[17px] shrink-0 text-muted" />
      <input
        ref={input}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={PLACEHOLDER}
        aria-label="Поиск по курсам"
        className="min-w-0 flex-1 bg-transparent py-[9px] text-[15.5px] text-ink outline-none placeholder:text-muted"
      />
      <button
        type="submit"
        className="rounded-full bg-ink px-[18px] py-2.5 text-sm font-medium text-bg transition-opacity hover:opacity-85 max-md:px-3.5"
      >
        Найти
      </button>
    </form>
  );
}
