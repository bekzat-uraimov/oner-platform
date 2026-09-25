"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { buttonClass } from "../button";
import { Enter, RiseWords } from "../motion";
import { Eyebrow, Spinner } from "../ui";
import type { MyPurchase } from "@/lib/api/types";
import { pendingCheckout } from "@/lib/checkout";
import { EASE } from "@/lib/motion";
import { useRequireUser } from "@/lib/use-require-user";
import { useSession } from "@/lib/session";

type Outcome = MyPurchase["status"] | "timeout";

const POLL_MS = 2500;
const POLL_TRIES = 24; // about a minute

export function CheckoutResult({ kind }: { kind: "success" | "failure" }) {
  const { allowed } = useRequireUser();
  const { request, refreshCourses } = useSession();
  const pending = allowed ? pendingCheckout() : null;
  const purchaseId = pending?.purchaseId ?? null;
  const [outcome, setOutcome] = useState<{ id: number; value: Outcome } | null>(null);

  // The redirect proves nothing; only the payment callback decides. Ask until it has.
  useEffect(() => {
    if (!allowed || kind !== "success" || purchaseId === null) return;
    let cancelled = false;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    const poll = () =>
      request<MyPurchase>(`/me/purchases/${purchaseId}`).then(
        (purchase) => {
          if (cancelled) return;
          if (purchase.status !== "pending") {
            setOutcome({ id: purchaseId, value: purchase.status });
            if (purchase.status === "paid") refreshCourses().catch(() => undefined);
            return;
          }
          tries += 1;
          if (tries >= POLL_TRIES) setOutcome({ id: purchaseId, value: "timeout" });
          else timer = setTimeout(poll, POLL_MS);
        },
        () => {
          if (!cancelled) timer = setTimeout(poll, POLL_MS);
        },
      );
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [allowed, kind, purchaseId, request, refreshCourses]);

  const slug = pending?.slug;
  const status: Outcome | "unknown" | "waiting" =
    kind === "failure" ? "failed" : purchaseId === null ? "unknown" : outcome?.id === purchaseId ? outcome.value : "waiting";

  const view = {
    waiting: { eyebrow: "Оплата", title: "Подтверждаем оплату", text: "Обычно это занимает несколько секунд. Не закрывайте страницу." },
    paid: { eyebrow: "Готово", title: "Оплата прошла", text: "Курс уже в «Моих курсах». Можно начинать." },
    refunded: { eyebrow: "Возврат", title: "Покупка возвращена", text: "Деньги по этой покупке вернули." },
    failed: { eyebrow: "Оплата", title: "Оплата не прошла", text: "Деньги не списаны. Попробуйте ещё раз или другой картой." },
    pending: { eyebrow: "Оплата", title: "Подтверждаем оплату", text: "" },
    timeout: {
      eyebrow: "Оплата",
      title: "Подтверждение задерживается",
      text: "Курс появится в «Моих курсах», как только банк подтвердит оплату. Если через час его там нет, напишите нам.",
    },
    unknown: { eyebrow: "Оплата", title: "Проверьте «Мои курсы»", text: "Оплаченный курс появляется там сразу после подтверждения." },
  }[status];

  return (
    <main className="hero-glow relative isolate grid min-h-[80vh] place-items-center px-0 pb-20 pt-28 text-center">
      <div className="wrap">
        {!allowed ? (
          <Spinner className="size-6 text-muted" />
        ) : (
          <>
            <Enter>
              <StatusMark status={status} />
            </Enter>
            <Enter delay={0.1}>
              <Eyebrow className="mt-6">{view.eyebrow}</Eyebrow>
            </Enter>
            <RiseWords key={status} text={view.title} delay={0.12} className="mx-auto mt-4 max-w-[18ch] text-[clamp(32px,5vw,56px)] font-semibold leading-[1.05] tracking-[-0.045em]" />
            <Enter delay={0.3}>
              <p className="mx-auto mt-4 max-w-[46ch] text-ink-2">{view.text}</p>
            </Enter>
            <Enter delay={0.4} className="mt-8 flex flex-wrap justify-center gap-3">
              {status === "paid" && slug && (
                <Link href={`/learn/${slug}`} className={buttonClass()}>
                  Начать обучение
                </Link>
              )}
              {status === "failed" && slug && (
                <Link href={`/courses/${slug}`} className={buttonClass()}>
                  Попробовать снова
                </Link>
              )}
              <Link href="/me" className={buttonClass(status === "paid" || status === "failed" ? "line" : "solid")}>
                Мои курсы
              </Link>
            </Enter>
          </>
        )}
      </div>
    </main>
  );
}

function StatusMark({ status }: { status: string }) {
  if (status === "waiting" || status === "pending") {
    return (
      <div className="mx-auto grid size-20 place-items-center rounded-full border border-line bg-bg shadow-lift">
        <Spinner className="size-7 text-ink" />
      </div>
    );
  }
  const good = status === "paid";
  return (
    <svg viewBox="0 0 52 52" className={`mx-auto size-20 ${good ? "text-green" : "text-muted"}`} aria-hidden>
      <motion.circle cx="26" cy="26" r="24" fill="none" stroke="currentColor" strokeWidth="2" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.6, ease: EASE }} />
      <motion.path
        d={good ? "M15 27l7 7 15-15" : "M18 18l16 16M34 18 18 34"}
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.4, ease: EASE, delay: 0.45 }}
      />
    </svg>
  );
}
