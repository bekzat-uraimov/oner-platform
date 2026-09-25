"use client";

import { LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { buttonClass } from "../button";
import { ArrowIcon, FileIcon, PlayIcon } from "../icons";
import { useToast } from "../toast";
import { EmptyState, ErrorNote, Eyebrow, Skeleton, Spinner } from "../ui";
import { ApiError } from "@/lib/api/catalog";
import type { CourseDetail, DrmToken, LessonDetail, MaterialDownload } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { formatClock, pad } from "@/lib/format";
import { EASE } from "@/lib/motion";
import { useApi } from "@/lib/use-api";
import { useRequireUser } from "@/lib/use-require-user";
import { useSession } from "@/lib/session";

type Material = LessonDetail["materials"][number];

export function LessonView({ slug, lessonId }: { slug: string; lessonId: number | null }) {
  const { allowed } = useRequireUser();
  const base = `/courses/${encodeURIComponent(slug)}`;
  const course = useApi<CourseDetail>(allowed ? base : null);
  const lessons = course.data ? course.data.modules.flatMap((module) => module.lessons) : [];
  const currentId = lessonId ?? lessons[0]?.id ?? null;
  const lesson = useApi<LessonDetail>(allowed && currentId ? `${base}/lessons/${currentId}` : null);
  const index = lessons.findIndex((l) => l.id === currentId);
  const previous = index > 0 ? lessons[index - 1] : null;
  const next = index >= 0 && index < lessons.length - 1 ? lessons[index + 1] : null;

  if (course.error) {
    return (
      <Shell>
        <EmptyState
          title={course.error.status === 404 ? "Курс не найден" : "Не удалось открыть курс"}
          text={course.error.status === 404 ? "Возможно, ссылка устарела." : describe(course.error)}
          action={<Link href="/me" className={buttonClass()}>Мои курсы</Link>}
        />
      </Shell>
    );
  }

  if (!course.data) {
    return (
      <Shell>
        <div className="grid gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Skeleton className="h-[420px] max-lg:hidden" />
          <div>
            <Skeleton className="aspect-video" />
            <Skeleton className="mt-6 h-8 w-2/3" />
          </div>
        </div>
      </Shell>
    );
  }

  const data = course.data;

  return (
    <Shell>
      <div className="grid gap-8 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="order-2 lg:order-1 lg:sticky lg:top-28 lg:self-start">
          <Link href={`/courses/${slug}`} className="group inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink">
            <ArrowIcon className="size-3.5 rotate-180 transition-transform group-hover:-translate-x-0.5" />
            О курсе
          </Link>
          <p className="mt-3 text-lg font-semibold leading-snug tracking-[-0.02em]">{data.title}</p>
          <LayoutGroup id="lesson-nav">
            <nav className="mt-5 flex max-h-[62vh] flex-col gap-5 overflow-y-auto pr-1">
              {data.modules.map((module, m) => (
                <div key={module.id}>
                  <Eyebrow className="mb-2 !text-muted">
                    {pad(m + 1)} — {module.title}
                  </Eyebrow>
                  <ul className="flex flex-col gap-0.5">
                    {module.lessons.map((item) => {
                      const active = item.id === currentId;
                      return (
                        <li key={item.id}>
                          <Link
                            href={`/learn/${slug}/${item.id}`}
                            className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                              active ? "text-bg" : "text-ink-2 hover:bg-surface-2 hover:text-ink"
                            }`}
                          >
                            {active && (
                              <motion.span layoutId="current-lesson" className="absolute inset-0 rounded-xl bg-ink" transition={{ duration: 0.4, ease: EASE }} />
                            )}
                            <span className="relative min-w-0 flex-1 truncate">{item.title}</span>
                            {item.duration ? <span className="relative font-mono text-xs opacity-70">{formatClock(item.duration)}</span> : null}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </nav>
          </LayoutGroup>
        </aside>

        <section className="order-1 min-w-0 lg:order-2">
          {lesson.error ? (
            lesson.error.status === 403 ? (
              <EmptyState
                title="Курс ещё не куплен"
                text="Уроки открываются сразу после оплаты."
                action={<Link href={`/courses/${slug}`} className={buttonClass()}>Перейти к покупке</Link>}
              />
            ) : (
              <ErrorNote error={lesson.error} onRetry={lesson.reload} />
            )
          ) : !lesson.data || lesson.data.id !== currentId ? (
            <>
              <Skeleton className="aspect-video" />
              <Skeleton className="mt-6 h-8 w-2/3" />
            </>
          ) : (
            <motion.div key={lesson.data.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: EASE }}>
              <Player lesson={lesson.data} cover={data.cover ?? null} />
              <div className="mt-7 flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <Eyebrow>Урок {pad(index + 1)} из {pad(lessons.length)}</Eyebrow>
                  <h1 className="mt-3 text-[clamp(26px,3.4vw,38px)] font-semibold leading-[1.1] tracking-[-0.035em]">{lesson.data.title}</h1>
                </div>
                {lesson.data.duration ? <span className="font-mono text-sm text-muted">{formatClock(lesson.data.duration)}</span> : null}
              </div>
              {lesson.data.description && <p className="mt-4 max-w-[64ch] text-[16px] leading-relaxed text-ink-2">{lesson.data.description}</p>}
              <Materials title="Материалы урока" items={lesson.data.materials} />
              <Materials title="Материалы курса" items={data.materials} />
              <div className="mt-10 flex flex-wrap justify-between gap-3 border-t border-line pt-6">
                {previous ? (
                  <Link href={`/learn/${slug}/${previous.id}`} className={buttonClass("line")}>
                    <ArrowIcon className="size-4 rotate-180" />
                    {previous.title}
                  </Link>
                ) : (
                  <span />
                )}
                {next && (
                  <Link href={`/learn/${slug}/${next.id}`} className={buttonClass("solid")}>
                    {next.title}
                    <ArrowIcon className="size-4" />
                  </Link>
                )}
              </div>
            </motion.div>
          )}
        </section>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-[80vh] pb-24 pt-[112px]">
      <div className="wrap">{children}</div>
    </main>
  );
}

function Player({ lesson, cover }: { lesson: LessonDetail; cover: string | null }) {
  const { request } = useSession();
  const [state, setState] = useState<{ lessonId: number; src?: string; error?: string; loading?: boolean } | null>(null);
  const current = state?.lessonId === lesson.id ? state : null;

  // A fresh token on every play: it lives ten minutes and is bound to this one video.
  async function play() {
    setState({ lessonId: lesson.id, loading: true });
    try {
      const token = await request<DrmToken>(`/video/${lesson.id}/token`, { method: "POST" });
      const src = `https://kinescope.io/embed/${encodeURIComponent(token.video_id)}?drmauthtoken=${encodeURIComponent(token.drm_auth_token)}&autoplay=1`;
      setState({ lessonId: lesson.id, src });
    } catch (e) {
      setState({ lessonId: lesson.id, error: describe(e, "Видео не загрузилось.") });
    }
  }

  return (
    <div className="relative aspect-video overflow-hidden rounded-[20px] border border-line bg-black shadow-float">
      {current?.src ? (
        <iframe
          src={current.src}
          title={lesson.title}
          allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
          allowFullScreen
          className="absolute inset-0 size-full"
        />
      ) : (
        <>
          {cover && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={cover} alt="" className="absolute inset-0 size-full scale-105 object-cover opacity-55 blur-[3px]" />
          )}
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(0,0,0,.15),rgba(0,0,0,.8))]" />
          <div className="relative grid size-full place-items-center p-6 text-center text-white">
            {lesson.video_available ? (
              <div className="flex flex-col items-center">
                <motion.button
                  type="button"
                  onClick={play}
                  disabled={current?.loading}
                  whileHover={{ scale: 1.07 }}
                  whileTap={{ scale: 0.94 }}
                  aria-label="Смотреть урок"
                  className="grid size-20 place-items-center rounded-full bg-white text-black shadow-[0_20px_60px_rgba(0,0,0,.5)]"
                >
                  {current?.loading ? <Spinner className="size-6" /> : <PlayIcon className="ml-1 size-7" />}
                </motion.button>
                {current?.error && <p className="mt-4 max-w-[40ch] text-sm text-white/85">{current.error}</p>}
              </div>
            ) : (
              <div>
                <p className="text-lg font-semibold">Видео скоро появится</p>
                <p className="mt-1 text-sm text-white/70">Автор ещё готовит этот урок.</p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Materials({ title, items }: { title: string; items: Material[] }) {
  const { request } = useSession();
  const toast = useToast();
  const [busy, setBusy] = useState<number | null>(null);

  if (items.length === 0) return null;

  // The link lives 60 seconds, so it's fetched on click and used at once.
  async function download(id: number) {
    setBusy(id);
    try {
      const file = await request<MaterialDownload>(`/materials/${id}/download`);
      window.location.assign(file.url);
    } catch (e) {
      toast(e instanceof ApiError ? describe(e) : "Не удалось скачать файл.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-8">
      <p className="mb-3 text-sm font-medium text-muted">{title}</p>
      <ul className="grid gap-2.5 sm:grid-cols-2">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => download(item.id)}
              disabled={busy === item.id}
              className="group flex w-full items-center gap-3 rounded-card border border-line bg-bg p-3.5 text-left transition-[border-color,box-shadow] hover:border-line-strong hover:shadow-lift"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-[11px] bg-surface-2 text-ink-2">
                {busy === item.id ? <Spinner /> : <FileIcon className="size-4" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] font-medium">{item.title}</span>
                <span className="font-mono text-[11px] uppercase text-muted">{item.type}</span>
              </span>
              <ArrowIcon className="size-4 rotate-90 text-muted transition group-hover:text-ink" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
