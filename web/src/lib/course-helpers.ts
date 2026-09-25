import type { CourseListItem } from "./api/types";
import type { CourseSummary } from "./catalog";

/** A list item shaped like a catalog card, for places without lesson totals. */
export function asSummary(course: CourseListItem): CourseSummary {
  return { ...course, lessons: 0, seconds: 0 };
}
