"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { CURRENCIES } from "./constants";
import { buttonClass } from "../button";
import { CourseArt } from "../course-art";
import { ArrowIcon, PlusIcon } from "../icons";
import { inputClass, selectClass } from "../input";
import { Badge, EmptyState, ErrorNote, Field, Modal, PageHead, Skeleton } from "../ui";
import type { CourseAdmin, CourseListItem, Currency } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { formatPrice, slugify } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { useSession } from "@/lib/session";

export function CoursesAdmin() {
  // With an admin token the catalog includes drafts.
  const courses = useApi<CourseListItem[]>("/courses");
  const [creating, setCreating] = useState(false);

  return (
    <div>
      <PageHead
        title="Курсы"
        count={courses.data?.length}
        action={
          <button type="button" onClick={() => setCreating(true)} className={buttonClass("solid", "sm")}>
            <PlusIcon className="size-3.5" />
            Новый курс
          </button>
        }
      />
      {courses.error && <ErrorNote error={courses.error} onRetry={courses.reload} />}
      {!courses.data ? (
        !courses.error && (
          <div className="grid gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[88px]" />
            ))}
          </div>
        )
      ) : courses.data.length === 0 ? (
        <EmptyState title="Курсов пока нет" text="Создайте первый курс: название, адрес и цена. Остальное заполните потом." />
      ) : (
        <ul className="grid gap-3">
          {courses.data.map((course) => (
            <li key={course.id}>
              <Link
                href={`/admin/courses/${course.id}`}
                className="group flex items-center gap-4 rounded-card border border-line bg-bg p-3 pr-5 transition-[border-color,box-shadow] duration-300 hover:border-line-strong hover:shadow-lift"
              >
                <div className="relative aspect-video w-28 shrink-0 overflow-hidden rounded-[10px] bg-surface sm:w-32">
                  <CourseArt title={course.title} cover={course.cover} segment={course.segment} className="absolute inset-0 size-full" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold tracking-[-0.01em]">{course.title}</p>
                  <p className="mt-0.5 truncate font-mono text-xs text-muted">
                    /{course.slug}
                    {course.segment ? ` · ${course.segment}` : ""}
                  </p>
                </div>
                <Badge tone={course.status === "published" ? "green" : "neutral"}>
                  {course.status === "published" ? "Опубликован" : "Черновик"}
                </Badge>
                <span className="w-24 text-right text-sm font-medium max-sm:hidden">{formatPrice(course.price, course.currency)}</span>
                <ArrowIcon className="size-4 shrink-0 text-muted transition group-hover:translate-x-0.5 group-hover:text-ink max-sm:hidden" />
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Modal open={creating} onClose={() => setCreating(false)} title="Новый курс">
        <CreateCourseForm />
      </Modal>
    </div>
  );
}

function CreateCourseForm() {
  const { request } = useSession();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState<string | null>(null);
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState<Currency>("KGS");
  const [segment, setSegment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const finalSlug = slug ?? slugify(title);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const course = await request<CourseAdmin>("/admin/courses", {
        method: "POST",
        json: { title: title.trim(), slug: finalSlug, price: price.trim() || "0", currency, segment: segment.trim() || null },
      });
      router.push(`/admin/courses/${course.id}`);
    } catch (err) {
      setError(describe(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4">
      <Field label="Название">
        <input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Цветокоррекция в DaVinci Resolve" className={inputClass} />
      </Field>
      <Field label="Адрес" hint="латиница, цифры и дефис">
        <input required value={finalSlug} onChange={(e) => setSlug(e.target.value)} className={`${inputClass} font-mono text-sm`} />
      </Field>
      <div className="grid grid-cols-[1fr_120px] gap-3">
        <Field label="Цена">
          <input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="12900" className={inputClass} />
        </Field>
        <Field label="Валюта">
          <select value={currency} onChange={(e) => setCurrency(e.target.value as Currency)} className={selectClass}>
            {CURRENCIES.map((code) => (
              <option key={code}>{code}</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Категория" hint="например, Цвет или Монтаж">
        <input value={segment} onChange={(e) => setSegment(e.target.value)} className={inputClass} />
      </Field>
      {error && <ErrorNote error={error} />}
      <p className="text-xs text-muted">Курс создаётся черновиком. Описание, обложку и программу добавите на следующем шаге.</p>
      <button type="submit" disabled={busy || !title.trim()} className={buttonClass("solid", "md", "w-full disabled:opacity-50")}>
        {busy ? "Создаём…" : "Создать курс"}
      </button>
    </form>
  );
}
