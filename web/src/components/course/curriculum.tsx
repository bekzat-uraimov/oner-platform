"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { ChevronIcon, FileIcon, LockIcon } from "../icons";
import type { CourseDetail } from "@/lib/api/catalog";
import { formatClock, LESSONS, plural } from "@/lib/format";
import { EASE } from "@/lib/motion";

type Module = CourseDetail["modules"][number];
type Lesson = Module["lessons"][number];

const pad = (n: number) => String(n).padStart(2, "0");

export function Curriculum({ modules }: { modules: Module[] }) {
  const [open, setOpen] = useState<number[]>(() => (modules[0] ? [modules[0].id] : []));
  // Lessons are numbered across the whole course, not per module.
  const starts = modules.map((_, i) => modules.slice(0, i).reduce((sum, m) => sum + m.lessons.length, 0));

  function toggle(id: number) {
    setOpen((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }

  return (
    <ol className="flex flex-col gap-3">
      {modules.map((module, i) => {
        const isOpen = open.includes(module.id);
        return (
          <li
            key={module.id}
            className={`overflow-hidden rounded-card border bg-bg transition-[border-color,box-shadow] duration-500 ${
              isOpen ? "border-line-strong shadow-lift" : "border-line"
            }`}
          >
            <button
              type="button"
              aria-expanded={isOpen}
              aria-controls={`module-${module.id}`}
              onClick={() => toggle(module.id)}
              className="flex w-full items-center gap-4 p-5 text-left transition-colors hover:bg-surface"
            >
              <span className="font-mono text-xs text-muted">{pad(i + 1)}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-[16.5px] font-semibold tracking-[-0.02em]">{module.title}</span>
                {module.description && <span className="mt-1 block text-sm text-muted">{module.description}</span>}
              </span>
              <span className="shrink-0 text-[13px] text-muted max-sm:hidden">
                {module.lessons.length} {plural(module.lessons.length, LESSONS)}
              </span>
              <motion.span
                animate={{ rotate: isOpen ? 180 : 0 }}
                transition={{ duration: 0.45, ease: EASE }}
                className="grid size-8 shrink-0 place-items-center rounded-full border border-line text-ink-2"
              >
                <ChevronIcon className="size-4" />
              </motion.span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  id={`module-${module.id}`}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.5, ease: EASE }}
                  className="overflow-hidden"
                >
                  <ul className="border-t border-line">
                    {module.lessons.map((lesson, j) => (
                      <LessonRow key={lesson.id} lesson={lesson} number={starts[i] + j + 1} delay={0.05 + j * 0.035} />
                    ))}
                  </ul>
                </motion.div>
              )}
            </AnimatePresence>
          </li>
        );
      })}
    </ol>
  );
}

function LessonRow({ lesson, number, delay }: { lesson: Lesson; number: number; delay: number }) {
  const files = lesson.materials ?? [];
  return (
    <motion.li
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay }}
      className="flex gap-4 border-b border-line px-5 py-4 last:border-b-0"
    >
      <span className="w-6 shrink-0 pt-0.5 font-mono text-xs text-muted">{pad(number)}</span>
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-medium">{lesson.title}</p>
        {lesson.description && <p className="mt-1 text-sm leading-relaxed text-muted">{lesson.description}</p>}
        {files.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {files.map((file) => (
              <li
                key={file.id}
                className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-2 py-1 text-xs text-ink-2"
              >
                <FileIcon className="size-3" />
                {file.title}
              </li>
            ))}
          </ul>
        )}
      </div>
      <span className="flex shrink-0 items-center gap-2 pt-0.5 text-muted">
        {lesson.duration ? <span className="font-mono text-xs">{formatClock(lesson.duration)}</span> : null}
        <LockIcon className="size-3.5" />
      </span>
    </motion.li>
  );
}
