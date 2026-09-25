import type { CourseDetail, CourseListItem } from "./api/catalog";

/** What a catalog card shows: the list item plus totals only the detail has. */
export type CourseSummary = CourseListItem & { lessons: number; seconds: number };

export function lessonsOf(detail: CourseDetail) {
  return (detail.modules ?? []).flatMap((module) => module.lessons ?? []);
}

export function summarize(course: CourseListItem, detail: CourseDetail | null): CourseSummary {
  const lessons = detail ? lessonsOf(detail) : [];
  return {
    ...course,
    lessons: lessons.length,
    seconds: lessons.reduce((sum, lesson) => sum + (lesson.duration ?? 0), 0),
  };
}
