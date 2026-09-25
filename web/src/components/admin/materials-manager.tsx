"use client";

import { useState } from "react";
import { ConfirmModal, type Confirmation } from "./confirm";
import { FileIcon, TrashIcon, UploadIcon } from "../icons";
import { useToast } from "../toast";
import { Badge, ErrorNote, ToolButton } from "../ui";
import type { MaterialAdmin, MaterialUploadTarget } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { useSession } from "@/lib/session";

type Parent = { course_id: number } | { lesson_id: number };
type Pending = { id: string; name: string; share: number; error?: string };

/** Straight to R2 with the presigned PUT, so the API never handles the bytes. */
function putFile(url: string, file: File, onProgress: (share: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => (xhr.status < 300 ? resolve() : reject(new Error(`Хранилище ответило ${xhr.status}`)));
    xhr.onerror = () => reject(new Error("Файл не дошёл до хранилища. Проверьте CORS бакета R2."));
    xhr.send(file);
  });
}

export function MaterialsManager({ parent, materials, onChange }: { parent: Parent; materials: MaterialAdmin[]; onChange: () => void }) {
  const { request } = useSession();
  const toast = useToast();
  const [pending, setPending] = useState<Pending[]>([]);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

  async function add(files: File[]) {
    for (const file of files) {
      const id = `${file.name}-${file.size}-${Date.now()}`;
      const update = (patch: Partial<Pending>) =>
        setPending((list) => list.map((item) => (item.id === id ? { ...item, ...patch } : item)));
      setPending((list) => [...list, { id, name: file.name, share: 0 }]);
      try {
        const target = await request<MaterialUploadTarget>("/admin/materials/upload-url", { method: "POST", json: { filename: file.name } });
        await putFile(target.url, file, (share) => update({ share }));
        await request("/admin/materials", {
          method: "POST",
          json: { title: file.name.replace(/\.[^.]+$/, ""), storage_key: target.storage_key, ...parent },
        });
        setPending((list) => list.filter((item) => item.id !== id));
        onChange();
      } catch (e) {
        update({ error: describe(e) });
      }
    }
  }

  async function rename(material: MaterialAdmin, title: string) {
    if (!title.trim() || title.trim() === material.title) return;
    try {
      await request(`/admin/materials/${material.id}`, { method: "PATCH", json: { title: title.trim() } });
      toast("Название сохранено");
      onChange();
    } catch (e) {
      toast(describe(e));
    }
  }

  return (
    <div className="grid gap-3">
      {materials.length > 0 && (
        <ul className="grid gap-2">
          {materials.map((material) => (
            <li key={material.id} className="flex items-center gap-3 rounded-card border border-line bg-bg p-2.5 pl-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-[10px] bg-surface-2 text-ink-2">
                <FileIcon className="size-4" />
              </span>
              <input
                defaultValue={material.title}
                aria-label="Название файла"
                onBlur={(e) => rename(material, e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
                className="min-w-0 flex-1 rounded-lg border border-transparent bg-transparent px-2 py-1.5 text-[15px] font-medium outline-none transition-colors hover:border-line focus:border-line-strong"
              />
              <Badge>{material.type}</Badge>
              <ToolButton
                label="Удалить файл"
                danger
                onClick={() =>
                  setConfirmation({
                    title: `Удалить «${material.title}»?`,
                    text: "Файл удалится из хранилища, скачать его будет нельзя.",
                    action: "Удалить",
                    run: async () => {
                      await request(`/admin/materials/${material.id}`, { method: "DELETE" });
                      onChange();
                    },
                  })
                }
              >
                <TrashIcon className="size-3.5" />
              </ToolButton>
            </li>
          ))}
        </ul>
      )}
      {pending.map((item) => (
        <div key={item.id} className="rounded-card border border-line p-3">
          <div className="flex justify-between gap-3 text-sm">
            <span className="truncate">{item.name}</span>
            <span className="font-mono text-xs text-muted">{item.error ? "ошибка" : `${Math.round(item.share * 100)}%`}</span>
          </div>
          {item.error ? (
            <div className="mt-2">
              <ErrorNote error={item.error} />
            </div>
          ) : (
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-ink transition-[width] duration-300" style={{ width: `${item.share * 100}%` }} />
            </div>
          )}
        </div>
      ))}
      <label className="flex cursor-pointer items-center justify-center gap-2 rounded-card border border-dashed border-line-strong px-4 py-4 text-sm font-medium text-muted transition-colors hover:bg-surface hover:text-ink">
        <UploadIcon className="size-4" />
        Добавить файлы: PDF, ZIP и другие
        <input
          type="file"
          multiple
          className="sr-only"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            e.target.value = "";
            if (files.length) add(files);
          }}
        />
      </label>
      <ConfirmModal confirmation={confirmation} onClose={() => setConfirmation(null)} />
    </div>
  );
}
