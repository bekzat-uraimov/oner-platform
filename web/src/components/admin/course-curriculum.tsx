"use client";

import { useState, type FormEvent } from "react";
import { ConfirmModal, type Confirmation } from "./confirm";
import { LessonEditor } from "./lesson-editor";
import { buttonClass } from "../button";
import { ChevronIcon, PencilIcon, PlusIcon, TrashIcon } from "../icons";
import { inputClass, textareaClass } from "../input";
import { useToast } from "../toast";
import { Badge, EmptyState, ErrorNote, Field, Modal, SectionHead, ToolButton } from "../ui";
import type { CourseAdmin, LessonAdmin, ModuleAdmin } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { FILES, LESSONS, MODULES, formatClock, pad, plural } from "@/lib/format";
import { useSession } from "@/lib/session";

type Ordered = { id: number; order: number };

export function VideoBadge({ lesson }: { lesson: LessonAdmin }) {
  if (lesson.pending_video_id) return <Badge tone="amber">видео обрабатывается</Badge>;
  if (lesson.kinescope_video_id) return <Badge tone="green">видео</Badge>;
  return <Badge>без видео</Badge>;
}

export function CourseCurriculum({ course, onChange }: { course: CourseAdmin; onChange: () => void }) {
  const { request } = useSession();
  const toast = useToast();
  const [moduleForm, setModuleForm] = useState<{ moduleId: number | null } | null>(null);
  const [lessonForm, setLessonForm] = useState<{ moduleId: number; lessonId: number | null } | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

  const modules = course.modules;
  const lessonCount = modules.reduce((sum, module) => sum + module.lessons.length, 0);
  const editingModule = moduleForm?.moduleId ? (modules.find((m) => m.id === moduleForm.moduleId) ?? null) : null;
  const lessonModule = lessonForm ? (modules.find((m) => m.id === lessonForm.moduleId) ?? null) : null;
  const editingLesson =
    lessonForm?.lessonId && lessonModule ? (lessonModule.lessons.find((l) => l.id === lessonForm.lessonId) ?? null) : null;

  // Swap two neighbours. Equal orders (older data) get their positions instead, or the swap would change nothing.
  async function move(kind: "modules" | "lessons", items: Ordered[], index: number, delta: -1 | 1) {
    const a = items[index];
    const b = items[index + delta];
    if (!b) return;
    const [orderA, orderB] = a.order === b.order ? [index + delta, index] : [b.order, a.order];
    try {
      await Promise.all([
        request(`/admin/${kind}/${a.id}`, { method: "PATCH", json: { order: orderA } }),
        request(`/admin/${kind}/${b.id}`, { method: "PATCH", json: { order: orderB } }),
      ]);
      onChange();
    } catch (e) {
      toast(describe(e));
    }
  }

  function removeModule(module: ModuleAdmin) {
    setConfirmation({
      title: `Удалить модуль «${module.title}»?`,
      text: `Удалятся ${module.lessons.length} ${plural(module.lessons.length, LESSONS)}, их материалы и видео, которые больше нигде не используются.`,
      action: "Удалить модуль",
      run: async () => {
        await request(`/admin/modules/${module.id}`, { method: "DELETE" });
        onChange();
      },
    });
  }

  function removeLesson(lesson: LessonAdmin) {
    setConfirmation({
      title: `Удалить урок «${lesson.title}»?`,
      text: "Удалятся материалы урока и его видео, если оно больше нигде не используется.",
      action: "Удалить урок",
      run: async () => {
        await request(`/admin/lessons/${lesson.id}`, { method: "DELETE" });
        onChange();
      },
    });
  }

  return (
    <section>
      <SectionHead
        title="Программа"
        hint={`${modules.length} ${plural(modules.length, MODULES)} · ${lessonCount} ${plural(lessonCount, LESSONS)}`}
        action={
          <button type="button" onClick={() => setModuleForm({ moduleId: null })} className={buttonClass("line", "sm")}>
            <PlusIcon className="size-3.5" />
            Модуль
          </button>
        }
      />
      {modules.length === 0 ? (
        <EmptyState
          title="Модулей пока нет"
          text="Модуль — это раздел курса, например «Основы цвета». Уроки добавляются внутрь модуля."
          action={
            <button type="button" onClick={() => setModuleForm({ moduleId: null })} className={buttonClass()}>
              Добавить модуль
            </button>
          }
        />
      ) : (
        <ol className="grid gap-4">
          {modules.map((module, i) => (
            <li key={module.id} className="overflow-hidden rounded-[18px] border border-line bg-bg">
              <div className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-5 py-4">
                <span className="font-mono text-xs text-muted">{pad(i + 1)}</span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold tracking-[-0.01em]">{module.title}</p>
                  {module.description && <p className="mt-0.5 text-sm text-muted">{module.description}</p>}
                </div>
                <div className="flex gap-1.5">
                  <ToolButton label="Выше" disabled={i === 0} onClick={() => move("modules", modules, i, -1)}>
                    <ChevronIcon className="size-4 rotate-180" />
                  </ToolButton>
                  <ToolButton label="Ниже" disabled={i === modules.length - 1} onClick={() => move("modules", modules, i, 1)}>
                    <ChevronIcon className="size-4" />
                  </ToolButton>
                  <ToolButton label="Изменить модуль" onClick={() => setModuleForm({ moduleId: module.id })}>
                    <PencilIcon className="size-3.5" />
                  </ToolButton>
                  <ToolButton label="Удалить модуль" danger onClick={() => removeModule(module)}>
                    <TrashIcon className="size-3.5" />
                  </ToolButton>
                </div>
              </div>
              <ul>
                {module.lessons.map((lesson, j) => (
                  <li key={lesson.id} className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3 last:border-b-0">
                    <span className="w-6 font-mono text-xs text-muted">{pad(j + 1)}</span>
                    <button
                      type="button"
                      onClick={() => setLessonForm({ moduleId: module.id, lessonId: lesson.id })}
                      className="group min-w-0 flex-1 text-left"
                    >
                      <span className="block truncate text-[15px] font-medium group-hover:underline group-hover:underline-offset-4">
                        {lesson.title}
                      </span>
                      <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <VideoBadge lesson={lesson} />
                        <Badge>{lesson.duration ? formatClock(lesson.duration) : "без длительности"}</Badge>
                        {lesson.materials.length > 0 && (
                          <Badge>
                            {lesson.materials.length} {plural(lesson.materials.length, FILES)}
                          </Badge>
                        )}
                      </span>
                    </button>
                    <div className="flex gap-1.5">
                      <ToolButton label="Выше" disabled={j === 0} onClick={() => move("lessons", module.lessons, j, -1)}>
                        <ChevronIcon className="size-4 rotate-180" />
                      </ToolButton>
                      <ToolButton label="Ниже" disabled={j === module.lessons.length - 1} onClick={() => move("lessons", module.lessons, j, 1)}>
                        <ChevronIcon className="size-4" />
                      </ToolButton>
                      <ToolButton label="Удалить урок" danger onClick={() => removeLesson(lesson)}>
                        <TrashIcon className="size-3.5" />
                      </ToolButton>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="px-5 py-3">
                <button
                  type="button"
                  onClick={() => setLessonForm({ moduleId: module.id, lessonId: null })}
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-muted transition-colors hover:text-ink"
                >
                  <PlusIcon className="size-3.5" />
                  Урок
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}

      <Modal open={moduleForm !== null} onClose={() => setModuleForm(null)} title={editingModule ? "Изменить модуль" : "Новый модуль"}>
        <ModuleForm
          key={editingModule?.id ?? "new"}
          courseId={course.id}
          module={editingModule}
          onDone={() => {
            onChange();
            setModuleForm(null);
          }}
        />
      </Modal>
      <LessonEditor
        open={lessonForm !== null}
        moduleId={lessonForm?.moduleId ?? null}
        lesson={editingLesson}
        onClose={() => setLessonForm(null)}
        onChange={onChange}
        onCreated={(lessonId) => setLessonForm((form) => (form ? { ...form, lessonId } : form))}
      />
      <ConfirmModal confirmation={confirmation} onClose={() => setConfirmation(null)} />
    </section>
  );
}

function ModuleForm({ courseId, module, onDone }: { courseId: number; module: ModuleAdmin | null; onDone: () => void }) {
  const { request } = useSession();
  const [title, setTitle] = useState(module?.title ?? "");
  const [description, setDescription] = useState(module?.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const json = { title: title.trim(), description: description.trim() || null };
    try {
      await request(module ? `/admin/modules/${module.id}` : `/admin/courses/${courseId}/modules`, {
        method: module ? "PATCH" : "POST",
        json,
      });
      onDone();
    } catch (err) {
      setError(describe(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <Field label="Название">
        <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Основы цвета" className={inputClass} />
      </Field>
      <Field label="Описание" hint="необязательно">
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} className={textareaClass} />
      </Field>
      {error && <ErrorNote error={error} />}
      <button type="submit" disabled={busy || !title.trim()} className={buttonClass("solid", "md", "w-full disabled:opacity-50")}>
        {busy ? "Сохраняем…" : module ? "Сохранить" : "Добавить модуль"}
      </button>
    </form>
  );
}
