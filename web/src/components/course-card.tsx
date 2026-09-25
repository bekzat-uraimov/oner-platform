import Link from "next/link";
import { CourseArt } from "./course-art";
import { ArrowIcon } from "./icons";
import { Tilt } from "./tilt";
import type { CourseSummary } from "@/lib/catalog";
import { formatLength, formatPrice, LESSONS, plural } from "@/lib/format";

export function CourseCard({ course, href, cta = "Смотреть программу" }: { course: CourseSummary; href?: string; cta?: string }) {
  const length = course.seconds ? ` · ${formatLength(course.seconds)}` : "";

  return (
    <Tilt className="flex flex-col overflow-hidden rounded-card border border-line bg-bg transition-[box-shadow,border-color] duration-500 ease-out-expo hover:border-line-strong hover:shadow-float">
      <Link href={href ?? `/courses/${course.slug}`} aria-label={course.title} className="absolute inset-0 z-[7] rounded-card" />

      <div className="relative aspect-video overflow-hidden border-b border-line bg-surface">
        <CourseArt title={course.title} cover={course.cover} segment={course.segment}
          className="absolute inset-0 h-full w-full transition-transform duration-700 ease-out-expo group-hover/tilt:scale-105"
        />
        <div className="absolute inset-x-3 bottom-3 z-[4] flex translate-y-2.5 opacity-0 transition duration-500 ease-out-expo group-hover/tilt:translate-y-0 group-hover/tilt:opacity-100 [@media(hover:none)]:translate-y-0 [@media(hover:none)]:opacity-100">
          <span className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-[9px] border border-line-strong bg-bg/90 px-2.5 py-2 text-[12.5px] font-medium text-ink backdrop-blur-md">
            {cta}
            <ArrowIcon className="size-3" />
          </span>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2.5 p-[17px] pb-[19px]">
        {/* The cover already names the topic, so the facts sit here instead of on top of it. */}
        {(course.segment || course.lessons > 0) && (
          <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
            {[course.segment, course.lessons > 0 ? `${course.lessons} ${plural(course.lessons, LESSONS)}${length}` : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
        <h3 className="text-[16.5px] font-semibold leading-[1.28] tracking-[-0.022em]">{course.title}</h3>
        {course.description && <p className="line-clamp-2 text-[13.5px] leading-relaxed text-muted">{course.description}</p>}
        <div className="mt-auto flex items-center justify-between border-t border-line pt-3">
          <span className="text-base font-semibold tracking-[-0.02em]">{formatPrice(course.price, course.currency)}</span>
          <span className="grid size-8 place-items-center rounded-full border border-line text-ink-2 transition duration-300 group-hover/tilt:border-ink group-hover/tilt:bg-ink group-hover/tilt:text-bg">
            <ArrowIcon className="size-3.5 -rotate-45 transition-transform duration-300 group-hover/tilt:rotate-0" />
          </span>
        </div>
      </div>
    </Tilt>
  );
}
