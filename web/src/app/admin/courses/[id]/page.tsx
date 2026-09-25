import { notFound } from "next/navigation";
import { CourseEditor } from "@/components/admin/course-editor";

export default async function AdminCoursePage(props: PageProps<"/admin/courses/[id]">) {
  const { id } = await props.params;
  const courseId = Number(id);
  if (!Number.isInteger(courseId) || courseId <= 0) notFound();
  return <CourseEditor courseId={courseId} />;
}
