"use client";

import { useState } from "react";
import { buttonClass } from "../button";
import { ErrorNote, Modal } from "../ui";
import { describe } from "@/lib/errors";

export type Confirmation = { title: string; text: string; action: string; run: () => Promise<void> };

/** "Are you sure?" for anything destructive. An error keeps the dialog open with the reason. */
export function ConfirmModal({ confirmation, onClose }: { confirmation: Confirmation | null; onClose: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setError(null);
    onClose();
  }

  async function confirm() {
    if (!confirmation) return;
    setBusy(true);
    setError(null);
    try {
      await confirmation.run();
      onClose();
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={confirmation !== null} onClose={close} title={confirmation?.title ?? ""} width="max-w-[460px]">
      <p className="text-[15px] leading-relaxed text-ink-2">{confirmation?.text}</p>
      {error && (
        <div className="mt-4">
          <ErrorNote error={error} />
        </div>
      )}
      <div className="mt-6 flex justify-end gap-2">
        <button type="button" onClick={close} className={buttonClass("line", "sm")}>
          Отмена
        </button>
        <button type="button" onClick={confirm} disabled={busy} className={buttonClass("danger", "sm", "disabled:opacity-60")}>
          {busy ? "Секунду…" : confirmation?.action}
        </button>
      </div>
    </Modal>
  );
}
