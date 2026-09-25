import type { Metadata } from "next";
import { MyCourses } from "@/components/student/my-courses";

export const metadata: Metadata = { title: "Мои курсы" };

export default function MyCoursesPage() {
  return <MyCourses />;
}
