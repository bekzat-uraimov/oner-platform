"use client";

import { useState } from "react";
import { ConfirmModal, type Confirmation } from "./confirm";
import { buttonClass } from "../button";
import { useToast } from "../toast";
import { cardClass, ErrorNote, PageHead } from "../ui";
import type { SweepReport } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { useSession } from "@/lib/session";

export function StorageAdmin() {
  const { request } = useSession();
  const toast = useToast();
  const [report, setReport] = useState<SweepReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

  async function run(apply: boolean) {
    setBusy(true);
    setError(null);
    try {
      const result = await request<SweepReport>(`/admin/storage/sweep?apply=${apply}`, { method: "POST" });
      setReport(result);
      if (apply) toast(`Удалено файлов: ${result.deleted}`);
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6">
      <PageHead title="Хранилище" />
      <div className={cardClass}>
        <p className="max-w-[64ch] text-[15px] leading-relaxed text-ink-2">
          Ищем файлы в R2, на которые не ссылается ни один материал: загрузки, которые так и не сохранили, или удаления, которые
          не дошли до хранилища. Файлы моложе 24 часов не трогаем, чтобы не удалить загрузку в процессе.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <button type="button" onClick={() => run(false)} disabled={busy} className={buttonClass("solid", "md", "disabled:opacity-60")}>
            {busy ? "Проверяем…" : "Проверить"}
          </button>
          {report && report.orphan_count > 0 && !report.applied && (
            <button
              type="button"
              onClick={() =>
                setConfirmation({
                  title: `Удалить ${report.orphan_count} файлов?`,
                  text: "Файлы удалятся из R2 навсегда.",
                  action: "Удалить",
                  run: () => run(true),
                })
              }
              className={buttonClass("line")}
            >
              Удалить {report.orphan_count}
            </button>
          )}
        </div>
      </div>
      {error && <ErrorNote error={error} />}
      {report && (
        <div className={cardClass}>
          <div className="grid grid-cols-3 gap-4 text-center">
            {[
              ["Проверено", report.scanned],
              ["Без материала", report.orphan_count],
              ["Удалено", report.deleted],
            ].map(([label, value]) => (
              <div key={label}>
                <p className="font-mono text-3xl font-semibold tracking-[-0.03em]">{value}</p>
                <p className="mt-1 text-xs text-muted">{label}</p>
              </div>
            ))}
          </div>
          {report.orphans.length > 0 && (
            <ul className="mt-5 max-h-72 overflow-y-auto rounded-xl border border-line font-mono text-xs">
              {report.orphans.map((key) => (
                <li key={key} className="border-b border-line px-3 py-2 last:border-b-0">
                  {key}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      <ConfirmModal confirmation={confirmation} onClose={() => setConfirmation(null)} />
    </div>
  );
}
