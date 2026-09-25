import type { Metadata } from "next";
import { LessonView } from "@/components/student/lesson-view";

export const metadata: Metadata = { title: "Обучение" };

export default async function CourseLearnPage(props: PageProps<"/learn/[slug]">) {
  const { slug } = await props.params;
  return <LessonView slug={slug} lessonId={null} />;
}
