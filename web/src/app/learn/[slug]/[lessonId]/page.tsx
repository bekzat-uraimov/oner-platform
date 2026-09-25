import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { LessonView } from "@/components/student/lesson-view";

export const metadata: Metadata = { title: "Обучение" };

export default async function LessonPage(props: PageProps<"/learn/[slug]/[lessonId]">) {
  const { slug, lessonId } = await props.params;
  const id = Number(lessonId);
  if (!Number.isInteger(id) || id <= 0) notFound();
  return <LessonView slug={slug} lessonId={id} />;
}
