"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { PURCHASE_STATUS } from "./constants";
import { buttonClass } from "../button";
import { textareaClass } from "../input";
import { useToast } from "../toast";
import { Badge, EmptyState, ErrorNote, Field, Modal } from "../ui";
import type { PurchaseAdmin } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { formatDate, formatPrice } from "@/lib/format";
import { useSession } from "@/lib/session";

export function PurchasesTable({ items, onChange, showUser = true }: { items: PurchaseAdmin[]; onChange: () => void; showUser?: boolean }) {
  const [refunding, setRefunding] = useState<PurchaseAdmin | null>(null);

  if (items.length === 0) {
    return <EmptyState title="Оплат нет" text="Здесь появятся все попытки оплаты: успешные, брошенные и возвраты." />;
  }

  return (
    <>
      <div className="overflow-x-auto rounded-[18px] border border-line">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line bg-surface text-xs text-muted">
            <tr>
              <th className="px-4 py-3 font-medium">Дата</th>
              {showUser && <th className="px-4 py-3 font-medium">Покупатель</th>}
              <th className="px-4 py-3 font-medium">Курс</th>
              <th className="px-4 py-3 text-right font-medium">Сумма</th>
              <th className="px-4 py-3 font-medium">Статус</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {items.map((purchase) => {
              const status = PURCHASE_STATUS[purchase.status];
              return (
                <tr key={purchase.id} className="border-b border-line align-top last:border-b-0">
                  <td className="whitespace-nowrap px-4 py-3 text-muted">{formatDate(purchase.created_at)}</td>
                  {showUser && (
                    <td className="px-4 py-3">
                      <Link href={`/admin/users/${purchase.user_id}`} className="hover:underline hover:underline-offset-4">
                        {purchase.user_email}
                      </Link>
                    </td>
                  )}
                  <td className="px-4 py-3">
                    <p className="font-medium">{purchase.course_title}</p>
                    <p className="mt-0.5 font-mono text-[11px] text-muted">
                      заказ #{purchase.id}
                      {purchase.gateway_txn_id ? ` · платёж ${purchase.gateway_txn_id}` : ""}
                    </p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{formatPrice(purchase.amount, purchase.currency)}</td>
                  <td className="px-4 py-3">
                    <Badge tone={status.tone}>{status.label}</Badge>
                    {purchase.refund_note && (
                      <p className="mt-1 max-w-[24ch] truncate text-xs text-muted" title={purchase.refund_note}>
                        {purchase.refund_note}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {purchase.status === "paid" && (
                      <button type="button" onClick={() => setRefunding(purchase)} className={buttonClass("line", "sm")}>
                        Возврат
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Modal open={refunding !== null} onClose={() => setRefunding(null)} title="Возврат оплаты">
        {refunding && (
          <RefundForm
            key={refunding.id}
            purchase={refunding}
            onDone={() => {
              onChange();
              setRefunding(null);
            }}
          />
        )}
      </Modal>
    </>
  );
}

const CHOICES = [
  { revoke: true, label: "Забрать курс", hint: "Уроки и материалы закроются сразу." },
  { revoke: false, label: "Оставить курс", hint: "Покупка отметится как возврат, доступ останется." },
] as const;

function RefundForm({ purchase, onDone }: { purchase: PurchaseAdmin; onDone: () => void }) {
  const { request } = useSession();
  const toast = useToast();
  const [revoke, setRevoke] = useState<boolean | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (revoke === null) return;
    setBusy(true);
    setError(null);
    try {
      await request(`/admin/purchases/${purchase.id}/refund`, { method: "POST", json: { revoke_access: revoke, note: note.trim() || null } });
      toast("Возврат записан");
      onDone();
    } catch (err) {
      setError(describe(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-5">
      <div className="rounded-card border border-[#f5d9a8] bg-[#fff8eb] p-4 text-sm leading-relaxed text-[#8a5a00] dark:border-[#4a3a17] dark:bg-[#1f1808] dark:text-[#f5c46b]">
        <p className="font-medium">Эта кнопка не отправляет деньги.</p>
        <p className="mt-1">Сначала верните оплату в кабинете FreedomPay, затем запишите возврат здесь.</p>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-mono text-xs">
          <dt>Заказ</dt>
          <dd>#{purchase.id}</dd>
          <dt>Платёж</dt>
          <dd>{purchase.gateway_txn_id ?? "—"}</dd>
          <dt>Сумма</dt>
          <dd>{formatPrice(purchase.amount, purchase.currency)}</dd>
        </dl>
      </div>
      <fieldset className="grid gap-2">
        <legend className="mb-2 text-sm font-medium">Доступ к курсу «{purchase.course_title}»</legend>
        {CHOICES.map((choice) => (
          <label
            key={choice.label}
            className={`flex cursor-pointer gap-3 rounded-card border p-3.5 transition-colors ${revoke === choice.revoke ? "border-ink bg-surface" : "border-line hover:bg-surface"}`}
          >
            <input type="radio" name="revoke" checked={revoke === choice.revoke} onChange={() => setRevoke(choice.revoke)} className="mt-1" />
            <span>
              <span className="block text-sm font-medium">{choice.label}</span>
              <span className="text-xs text-muted">{choice.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>
      <Field label="Заметка" hint="необязательно">
        <textarea
          value={note}
          maxLength={500}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Например: вернули в кабинете FreedomPay, обращение №42"
          className={textareaClass}
        />
      </Field>
      {error && <ErrorNote error={error} />}
      <button type="submit" disabled={busy || revoke === null} className={buttonClass("solid", "md", "w-full disabled:opacity-40")}>
        {busy ? "Записываем…" : "Записать возврат"}
      </button>
    </form>
  );
}
