"use client";

import { useEffect } from "react";
import { ButtonLink } from "../button";
import { CourseCard } from "../course-card";
import { Enter, Reveal, RiseWords } from "../motion";
import { EmptyState, Eyebrow, Skeleton } from "../ui";
import { asSummary } from "@/lib/course-helpers";
import { useRequireUser } from "@/lib/use-require-user";
import { useSession } from "@/lib/session";

export function MyCourses() {
  const { allowed } = useRequireUser();
  const { courses, refreshCourses } = useSession();

  // Catch purchases that settled since sign-in.
  useEffect(() => {
    if (allowed) refreshCourses().catch(() => undefined);
  }, [allowed, refreshCourses]);

  return (
    <main className="hero-glow relative isolate min-h-[75vh] pb-24 pt-[136px]">
      <div className="wrap">
        <Enter>
          <Eyebrow>Кабинет</Eyebrow>
        </Enter>
        <RiseWords text="Мои курсы" className="mt-4 text-[clamp(36px,5vw,58px)] font-semibold tracking-[-0.045em]" />
        <div className="mt-10">
          {!allowed || !courses ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(min(320px,100%),1fr))] gap-[22px]">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="aspect-[4/3.4]" />
              ))}
            </div>
          ) : courses.length === 0 ? (
            <Reveal>
              <EmptyState
                title="Пока пусто"
                text="Купленные курсы появляются здесь сразу после оплаты."
                action={<ButtonLink href="/#courses">Смотреть каталог</ButtonLink>}
              />
            </Reveal>
          ) : (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(min(320px,100%),1fr))] gap-[22px]">
              {courses.map((course, i) => (
                <Reveal key={course.id} delay={Math.min(i * 0.06, 0.3)}>
                  <CourseCard course={asSummary(course)} href={`/learn/${course.slug}`} cta="Продолжить обучение" />
                </Reveal>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
