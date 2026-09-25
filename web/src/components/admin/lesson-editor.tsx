"use client";

import { useState, type FormEvent } from "react";
import { MaterialsManager } from "./materials-manager";
import { VideoPanel } from "./video-panel";
import { buttonClass } from "../button";
import { inputClass, textareaClass } from "../input";
import { ErrorNote, Field, Modal } from "../ui";
import type { LessonAdmin } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { formatClock, parseClock } from "@/lib/format";
import { useSession } from "@/lib/session";

type Tab = "details" | "video" | "materials";

const TABS: [Tab, string][] = [
  ["details", "Основное"],
  ["video", "Видео"],
  ["materials", "Материалы"],
];

export function LessonEditor({
  open,
  moduleId,
  lesson,
  onClose,
  onChange,
  onCreated,
}: {
  open: boolean;
  moduleId: number | null;
  lesson: LessonAdmin | null;
  onClose: () => void;
  onChange: () => void;
  onCreated: (lessonId: number) => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title={lesson ? lesson.title : "Новый урок"} width="max-w-[660px]">
      {lesson ? (
        <LessonTabs key={lesson.id} lesson={lesson} onChange={onChange} />
      ) : (
        <LessonDetails
          key={`new-${moduleId}`}
          moduleId={moduleId}
          lesson={null}
          onSaved={(created) => {
            onChange();
            if (created) onCreated(created);
          }}
        />
      )}
    </Modal>
  );
}

function LessonTabs({ lesson, onChange }: { lesson: LessonAdmin; onChange: () => void }) {
  const [tab, setTab] = useState<Tab>("details");
  return (
    <div>
      {/* A plain highlight: a shared-layout pill mismeasures while the dialog is still scaling in. */}
      <div role="tablist" className="mb-5 inline-flex rounded-full border border-line p-1">
        {TABS.map(([value, label]) => {
          const selected = value === tab;
          return (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setTab(value)}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors duration-300 ${
                selected ? "bg-ink text-bg" : "text-muted hover:text-ink"
              }`}
            >
              {label}
            </button>
          );
        })}
      </div>
      {tab === "details" && <LessonDetails moduleId={lesson.module_id} lesson={lesson} onSaved={() => onChange()} />}
      {tab === "video" && <VideoPanel lesson={lesson} onChange={onChange} />}
      {tab === "materials" && <MaterialsManager parent={{ lesson_id: lesson.id }} materials={lesson.materials} onChange={onChange} />}
    </div>
  );
}

function LessonDetails({
  moduleId,
  lesson,
  onSaved,
}: {
  moduleId: number | null;
  lesson: LessonAdmin | null;
  onSaved: (createdId?: number) => void;
}) {
  const { request } = useSession();
  const [title, setTitle] = useState(lesson?.title ?? "");
  const [description, setDescription] = useState(lesson?.description ?? "");
  const [duration, setDuration] = useState(lesson?.duration ? formatClock(lesson.duration) : "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const seconds = parseClock(duration);
  const durationError = Number.isNaN(seconds) ? "Формат мм:сс, например 7:30" : null;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (durationError) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    const json = { title: title.trim(), description: description.trim() || null, duration: seconds };
    try {
      if (lesson) {
        await request(`/admin/lessons/${lesson.id}`, { method: "PATCH", json });
        setSaved(true);
        onSaved();
      } else {
        const created = await request<LessonAdmin>(`/admin/modules/${moduleId}/lessons`, { method: "POST", json });
        onSaved(created.id);
      }
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <Field label="Название">
        <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Баланс белого и экспозиция" className={inputClass} />
      </Field>
      <Field label="Описание" hint="что будет в уроке">
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} className={textareaClass} />
      </Field>
      <Field label="Длительность" hint="мм:сс" error={durationError}>
        <input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="7:30" className={`${inputClass} max-w-[160px] font-mono`} />
      </Field>
      {error && <ErrorNote error={error} />}
      {!lesson && <p className="text-xs text-muted">Видео и материалы добавите сразу после создания урока.</p>}
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !title.trim()} className={buttonClass("solid", "md", "disabled:opacity-50")}>
          {busy ? "Сохраняем…" : lesson ? "Сохранить" : "Создать урок"}
        </button>
        {saved && <span className="text-sm text-green">Сохранено</span>}
      </div>
    </form>
  );
}
