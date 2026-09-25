"use client";

import { useEffect, useRef, useState } from "react";
import type { Upload } from "tus-js-client";
import { buttonClass } from "../button";
import { UploadIcon } from "../icons";
import { inputClass } from "../input";
import { useToast } from "../toast";
import { Badge, ErrorNote, Field, Spinner } from "../ui";
import type { LessonAdmin, LessonVideo, VideoUploadTarget } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { useApi } from "@/lib/use-api";
import { useSession } from "@/lib/session";

type Progress = { share: number; error?: string; done?: boolean };

const STATE = {
  in_progress: { label: "Обрабатывается", tone: "amber" },
  complete: { label: "Готово", tone: "green" },
  failed: { label: "Ошибка обработки", tone: "red" },
} as const;

export function VideoPanel({ lesson, onChange }: { lesson: LessonAdmin; onChange: () => void }) {
  const { request } = useSession();
  const toast = useToast();
  const video = useApi<LessonVideo>(`/admin/lessons/${lesson.id}/video`);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [linkId, setLinkId] = useState(lesson.kinescope_video_id ?? "");
  const [busy, setBusy] = useState(false);
  const upload = useRef<Upload | null>(null);
  const uploading = progress !== null && !progress.done && !progress.error;
  const state = video.data?.state ?? null;
  const reloadVideo = video.reload;

  // Kinescope processes the file after the upload; check every few seconds until it settles.
  useEffect(() => {
    if (state !== "in_progress" || uploading) return;
    const timer = setInterval(reloadVideo, 6000);
    return () => clearInterval(timer);
  }, [state, uploading, reloadVideo]);

  // Once processing finishes the API swaps the video into the lesson, so the editor refetches it.
  const swapped = state === "complete" && lesson.pending_video_id != null;
  useEffect(() => {
    if (swapped) onChange();
  }, [swapped, onChange]);

  useEffect(() => {
    if (!uploading) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [uploading]);

  useEffect(() => {
    return () => {
      upload.current?.abort();
    };
  }, []);

  async function start(file: File) {
    setProgress({ share: 0 });
    let target: VideoUploadTarget;
    try {
      target = await request<VideoUploadTarget>(`/admin/lessons/${lesson.id}/video/upload`, {
        method: "POST",
        json: { filename: file.name, filesize: file.size },
      });
    } catch (e) {
      setProgress({ share: 0, error: describe(e) });
      return;
    }
    // Loaded only when someone actually uploads. The endpoint is the upload Kinescope
    // already created, so it's resumed rather than created again.
    const tus = await import("tus-js-client");
    const task = new tus.Upload(file, {
      uploadUrl: target.endpoint,
      chunkSize: 50 * 1024 * 1024,
      retryDelays: [0, 3000, 10000, 20000],
      metadata: { filename: file.name, filetype: file.type },
      onProgress: (sent, total) => setProgress({ share: total ? sent / total : 0 }),
      onError: (error) => setProgress({ share: 0, error: `Загрузка прервалась: ${error.message}` }),
      onSuccess: () => {
        setProgress({ share: 1, done: true });
        reloadVideo();
        onChange();
      },
    });
    upload.current = task;
    task.start();
  }

  async function link(id: string | null) {
    setBusy(true);
    try {
      await request(`/admin/lessons/${lesson.id}`, { method: "PATCH", json: { kinescope_video_id: id } });
      toast(id ? "Видео привязано" : "Видео отвязано");
      onChange();
      reloadVideo();
    } catch (e) {
      toast(describe(e));
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    try {
      await request(`/admin/lessons/${lesson.id}/video/pending`, { method: "DELETE" });
      toast("Загрузка отменена");
      setProgress(null);
      onChange();
      reloadVideo();
    } catch (e) {
      toast(describe(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-5">
      <div className="rounded-card border border-line bg-surface p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Сейчас в уроке</p>
            <p className="mt-1 font-mono text-xs text-muted">{lesson.kinescope_video_id ?? "видео нет"}</p>
          </div>
          {video.loading && !video.data ? (
            <Spinner className="size-4 text-muted" />
          ) : (
            state && <Badge tone={STATE[state].tone}>{STATE[state].label}</Badge>
          )}
        </div>
        {lesson.pending_video_id && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3 text-sm">
            <span className="text-muted">
              Новая загрузка: <span className="font-mono text-xs">{lesson.pending_video_id}</span>
              {video.data?.pending_status ? ` · ${video.data.pending_status}` : ""}
            </span>
            <button type="button" onClick={discard} disabled={busy} className={buttonClass("line", "sm")}>
              Отменить загрузку
            </button>
          </div>
        )}
        {video.error && (
          <div className="mt-3">
            <ErrorNote error={video.error} onRetry={reloadVideo} />
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-sm font-medium">Загрузить видео в Kinescope</p>
        {uploading ? (
          <div className="rounded-card border border-line p-4">
            <div className="flex justify-between text-sm">
              <span>Загружаем…</span>
              <span className="font-mono">{Math.round(progress.share * 100)}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-ink transition-[width] duration-300" style={{ width: `${progress.share * 100}%` }} />
            </div>
            <p className="mt-2 text-xs text-muted">Не закрывайте окно до конца загрузки.</p>
          </div>
        ) : (
          <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-card border border-dashed border-line-strong px-6 py-8 text-center transition-colors hover:bg-surface">
            <UploadIcon className="size-5 text-muted" />
            <span className="text-sm font-medium">Выберите видеофайл</span>
            <span className="max-w-[46ch] text-xs text-muted">
              Файл уходит напрямую в Kinescope. Студенты увидят новое видео, когда Kinescope его обработает.
            </span>
            <input
              type="file"
              accept="video/*"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                e.target.value = "";
                if (file) start(file);
              }}
            />
          </label>
        )}
        {progress?.error && (
          <div className="mt-3">
            <ErrorNote error={progress.error} />
          </div>
        )}
        {progress?.done && <p className="mt-3 text-sm text-green">Файл загружен. Kinescope обрабатывает видео.</p>}
      </div>

      <Field label="Или привяжите готовое видео" hint="ID видео в Kinescope">
        <span className="flex gap-2">
          <input value={linkId} onChange={(e) => setLinkId(e.target.value)} placeholder="ID из кабинета Kinescope" className={`${inputClass} font-mono text-sm`} />
          <button
            type="button"
            disabled={busy || !linkId.trim() || linkId.trim() === lesson.kinescope_video_id}
            onClick={() => link(linkId.trim())}
            className={buttonClass("solid", "md", "disabled:opacity-40")}
          >
            Привязать
          </button>
        </span>
      </Field>
      {lesson.kinescope_video_id && (
        <button type="button" onClick={() => link(null)} disabled={busy} className="justify-self-start text-sm text-muted underline-offset-4 hover:text-ink hover:underline">
          Отвязать видео от урока
        </button>
      )}
    </div>
  );
}
