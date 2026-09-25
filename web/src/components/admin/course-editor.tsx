"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ConfirmModal, type Confirmation } from "./confirm";
import { CURRENCIES } from "./constants";
import { CourseCurriculum } from "./course-curriculum";
import { MaterialsManager } from "./materials-manager";
import { buttonClass } from "../button";
import { CourseArt } from "../course-art";
import { ExternalIcon } from "../icons";
import { inputClass, selectClass, textareaClass } from "../input";
import { useToast } from "../toast";
import { Badge, cardClass, EmptyState, ErrorNote, Field, SectionHead, Skeleton } from "../ui";
import type { CourseAdmin } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { useApi } from "@/lib/use-api";
import { useSession } from "@/lib/session";

export function CourseEditor({ courseId }: { courseId: number }) {
  const course = useApi<CourseAdmin>(`/admin/courses/${courseId}`);

  if (course.error && !course.data) {
    return course.error.status === 404 ? (
      <EmptyState title="Курс не найден" action={<Link href="/admin/courses" className={buttonClass()}>Все курсы</Link>} />
    ) : (
      <ErrorNote error={course.error} onRetry={course.reload} />
    );
  }
  if (!course.data) {
    return (
      <div className="grid gap-4">
        <Skeleton className="h-24" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="grid gap-10">
      <EditorHeader course={course.data} onChange={course.reload} />
      <DetailsForm key={course.data.id} course={course.data} onSaved={course.reload} />
      <CourseCurriculum course={course.data} onChange={course.reload} />
      <section>
        <SectionHead title="Материалы курса" hint="Общие файлы курса, не привязанные к уроку. Скачиваются только после покупки." />
        <MaterialsManager parent={{ course_id: course.data.id }} materials={course.data.materials} onChange={course.reload} />
      </section>
    </div>
  );
}

function EditorHeader({ course, onChange }: { course: CourseAdmin; onChange: () => void }) {
  const { request } = useSession();
  const toast = useToast();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const published = course.status === "published";

  async function togglePublish() {
    setBusy(true);
    try {
      await request(`/admin/courses/${course.id}`, { method: "PATCH", json: { status: published ? "draft" : "published" } });
      toast(published ? "Курс снят с публикации" : "Курс опубликован");
      onChange();
    } catch (e) {
      toast(describe(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Link href="/admin/courses" className="text-sm text-muted transition-colors hover:text-ink">
        ← Все курсы
      </Link>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-5">
        <div className="flex min-w-0 items-center gap-4">
          <div className="relative aspect-video w-36 shrink-0 overflow-hidden rounded-xl border border-line max-sm:hidden">
            <CourseArt title={course.title} cover={course.cover} segment={course.segment} className="absolute inset-0 size-full" />
          </div>
          <div className="min-w-0">
            <h1 className="text-[clamp(24px,3.2vw,34px)] font-semibold leading-tight tracking-[-0.035em]">{course.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone={published ? "green" : "neutral"}>{published ? "Опубликован" : "Черновик"}</Badge>
              <Link href={`/courses/${course.slug}`} target="_blank" className="inline-flex items-center gap-1 font-mono text-xs text-muted hover:text-ink">
                /courses/{course.slug}
                <ExternalIcon className="size-3" />
              </Link>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={togglePublish} disabled={busy} className={buttonClass(published ? "line" : "solid", "sm")}>
            {published ? "Снять с публикации" : "Опубликовать"}
          </button>
          <button
            type="button"
            onClick={() =>
              setConfirmation({
                title: "Удалить курс?",
                text: "Удалятся модули, уроки, файлы материалов и видео, которые больше нигде не используются. Курс, который уже покупали, удалить нельзя: его снимают с публикации.",
                action: "Удалить курс",
                run: async () => {
                  await request(`/admin/courses/${course.id}`, { method: "DELETE" });
                  toast("Курс удалён");
                  router.push("/admin/courses");
                },
              })
            }
            className={buttonClass("line", "sm")}
          >
            Удалить
          </button>
        </div>
      </div>
      {!published && (
        <p className="mt-4 text-sm text-muted">Черновик видят только администраторы. Опубликуйте курс, когда программа будет готова.</p>
      )}
      <ConfirmModal confirmation={confirmation} onClose={() => setConfirmation(null)} />
    </div>
  );
}

type Draft = {
  title: string;
  slug: string;
  segment: string;
  price: string;
  currency: string;
  cover: string;
  description: string;
  learning_outcomes: string;
  requirements: string;
};

// Emptied, these are sent as null; the rest the API requires.
const OPTIONAL = new Set<keyof Draft>(["segment", "cover", "description", "learning_outcomes", "requirements"]);

function toDraft(course: CourseAdmin): Draft {
  return {
    title: course.title,
    slug: course.slug,
    segment: course.segment ?? "",
    price: String(Number(course.price)),
    currency: course.currency,
    cover: course.cover ?? "",
    description: course.description ?? "",
    learning_outcomes: course.learning_outcomes ?? "",
    requirements: course.requirements ?? "",
  };
}

function DetailsForm({ course, onSaved }: { course: CourseAdmin; onSaved: () => void }) {
  const { request } = useSession();
  const toast = useToast();
  const [draft, setDraft] = useState<Draft>(() => toDraft(course));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const base = toDraft(course);
  const changed = (Object.keys(draft) as (keyof Draft)[]).filter((key) => draft[key].trim() !== base[key]);

  function update(key: keyof Draft, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (changed.length === 0) return;
    const patch = Object.fromEntries(changed.map((key) => [key, OPTIONAL.has(key) && !draft[key].trim() ? null : draft[key].trim()]));
    setBusy(true);
    setError(null);
    try {
      await request(`/admin/courses/${course.id}`, { method: "PATCH", json: patch });
      toast("Сохранено");
      onSaved();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className={cardClass}>
      <SectionHead
        title="О курсе"
        hint="То, что видят на странице курса."
        action={
          <button type="submit" disabled={busy || changed.length === 0} className={buttonClass("solid", "sm", "disabled:opacity-40")}>
            {busy ? "Сохраняем…" : changed.length ? `Сохранить (${changed.length})` : "Сохранено"}
          </button>
        }
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Название">
          <input required value={draft.title} onChange={(e) => update("title", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Адрес" hint="/courses/…">
          <input required value={draft.slug} onChange={(e) => update("slug", e.target.value)} className={`${inputClass} font-mono text-sm`} />
        </Field>
        <Field label="Категория">
          <input value={draft.segment} onChange={(e) => update("segment", e.target.value)} className={inputClass} />
        </Field>
        <div className="grid grid-cols-[1fr_110px] gap-3">
          <Field label="Цена">
            <input required inputMode="decimal" value={draft.price} onChange={(e) => update("price", e.target.value)} className={inputClass} />
          </Field>
          <Field label="Валюта">
            <select value={draft.currency} onChange={(e) => update("currency", e.target.value)} className={selectClass}>
              {CURRENCIES.map((code) => (
                <option key={code}>{code}</option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Обложка" hint="ссылка на картинку 16:9" className="md:col-span-2">
          <span className="flex items-center gap-3">
            <input
              value={draft.cover}
              onChange={(e) => update("cover", e.target.value)}
              placeholder="/covers/salym.jpg или https://…"
              className={inputClass}
            />
            {draft.cover.trim() && (
              <>
                {/* Any host an admin pastes, so a plain img. */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={draft.cover.trim()} alt="" className="aspect-video h-[50px] shrink-0 rounded-lg border border-line object-cover" />
              </>
            )}
          </span>
        </Field>
        <Field label="Описание" className="md:col-span-2">
          <textarea value={draft.description} onChange={(e) => update("description", e.target.value)} className={textareaClass} />
        </Field>
        <Field label="Чему научатся" hint="по пункту в строке">
          <textarea value={draft.learning_outcomes} onChange={(e) => update("learning_outcomes", e.target.value)} rows={5} className={textareaClass} />
        </Field>
        <Field label="Что понадобится" hint="по пункту в строке">
          <textarea value={draft.requirements} onChange={(e) => update("requirements", e.target.value)} rows={5} className={textareaClass} />
        </Field>
      </div>
      {error && (
        <div className="mt-4">
          <ErrorNote error={error} />
        </div>
      )}
    </form>
  );
}
