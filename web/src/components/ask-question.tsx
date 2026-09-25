"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { buttonClass, type ButtonSize, type ButtonVariant } from "./button";
import { PlusIcon } from "./icons";
import { inputClass } from "./input";
import { EASE } from "@/lib/motion";
import { useSession } from "@/lib/session";

type Step = "question" | "email" | "sent";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_LENGTH = 10;
const STORE = "oner-questions";

const slide = {
  initial: { opacity: 0, x: 24 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -24 },
  transition: { duration: 0.35, ease: EASE },
};

export function AskQuestion({
  label = "Задать вопрос",
  variant = "solid",
  size = "md",
}: {
  label?: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
}) {
  const [open, setOpen] = useState(false);
  // The portal needs document.body, which only exists after a click in the browser.
  const [opened, setOpened] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpened(true);
          setOpen(true);
        }}
        className={buttonClass(variant, size)}
      >
        {label}
      </button>
      {opened &&
        createPortal(
          <AnimatePresence>{open && <QuestionDialog key="dialog" onClose={() => setOpen(false)} />}</AnimatePresence>,
          document.body,
        )}
    </>
  );
}

function QuestionDialog({ onClose }: { onClose: () => void }) {
  const { user } = useSession();
  const [step, setStep] = useState<Step>("question");
  const [question, setQuestion] = useState("");
  const [email, setEmail] = useState(user?.email ?? "");
  const [emailTouched, setEmailTouched] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const emailInput = useRef<HTMLInputElement>(null);

  const questionOk = question.trim().length >= MIN_LENGTH;
  const emailOk = EMAIL.test(email.trim());

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  useEffect(() => {
    const timer = setTimeout(() => (step === "question" ? textarea : emailInput).current?.focus(), 80);
    return () => clearTimeout(timer);
  }, [step]);

  function send() {
    // Not delivered anywhere yet: kept in this tab until the backend has a
    // questions endpoint (or a Telegram bot) to send it to.
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORE) ?? "[]");
      saved.push({ question: question.trim(), email: email.trim(), at: new Date().toISOString() });
      sessionStorage.setItem(STORE, JSON.stringify(saved));
    } catch {
      // Storage blocked: nothing to keep.
    }
    setStep("sent");
  }

  return (
    <motion.div
      className="fixed inset-0 z-[400] flex items-end justify-center p-3 sm:items-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div aria-hidden onClick={onClose} className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="ask-title"
        initial={{ y: 40, scale: 0.96, opacity: 0, filter: "blur(8px)" }}
        animate={{ y: 0, scale: 1, opacity: 1, filter: "blur(0px)" }}
        exit={{ y: 24, scale: 0.97, opacity: 0 }}
        transition={{ duration: 0.5, ease: EASE }}
        className="relative w-full max-w-[480px] overflow-hidden rounded-[22px] border border-line bg-bg p-6 shadow-float sm:p-7"
      >
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-muted">
            {step === "sent" ? "Готово" : `Шаг ${step === "question" ? 1 : 2} из 2`}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="grid size-8 place-items-center rounded-full border border-line text-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <PlusIcon className="size-3.5 rotate-45" />
          </button>
        </div>
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-surface-2">
          <motion.div
            className="h-full rounded-full bg-ink"
            initial={false}
            animate={{ width: step === "question" ? "50%" : "100%" }}
            transition={{ duration: 0.6, ease: EASE }}
          />
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {step === "question" && (
            <motion.form
              key="question"
              {...slide}
              onSubmit={(e) => {
                e.preventDefault();
                if (questionOk) setStep("email");
              }}
              className="mt-6"
            >
              <h2 id="ask-title" className="text-2xl font-semibold tracking-[-0.03em]">
                Какой у вас вопрос?
              </h2>
              <p className="mt-2 text-sm text-muted">Про курсы, оплату или доступ. Пишите как есть.</p>
              <textarea
                ref={textarea}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={5}
                maxLength={1000}
                aria-label="Ваш вопрос"
                placeholder="Например: подойдёт ли курс, если я снимаю только на телефон?"
                className={`${inputClass} mt-5 resize-none`}
              />
              <div className="mt-2 flex justify-between text-xs text-muted">
                <span>{questionOk ? "" : `Минимум ${MIN_LENGTH} символов`}</span>
                <span className="font-mono">{question.length}/1000</span>
              </div>
              <button
                type="submit"
                disabled={!questionOk}
                className={buttonClass("solid", "md", "mt-5 w-full disabled:cursor-not-allowed disabled:opacity-40")}
              >
                Дальше
              </button>
            </motion.form>
          )}

          {step === "email" && (
            <motion.form
              key="email"
              {...slide}
              onSubmit={(e) => {
                e.preventDefault();
                setEmailTouched(true);
                if (emailOk) send();
              }}
              className="mt-6"
            >
              <h2 id="ask-title" className="text-2xl font-semibold tracking-[-0.03em]">
                Куда прислать ответ?
              </h2>
              <p className="mt-2 text-sm text-muted">Ответим на почту. Больше ничего туда не отправим.</p>
              <input
                ref={emailInput}
                type="email"
                inputMode="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onBlur={() => setEmailTouched(true)}
                aria-label="Почта"
                aria-invalid={emailTouched && !emailOk}
                placeholder="you@mail.ru"
                className={`${inputClass} mt-5`}
              />
              <p className="mt-2 h-4 text-xs text-[#b42318] dark:text-[#ff9a8f]">
                {emailTouched && !emailOk ? "Проверьте адрес почты" : ""}
              </p>
              <div className="mt-4 flex gap-2.5">
                <button type="button" onClick={() => setStep("question")} className={buttonClass("line")}>
                  Назад
                </button>
                <button type="submit" className={buttonClass("solid", "md", "flex-1")}>
                  Отправить
                </button>
              </div>
            </motion.form>
          )}

          {step === "sent" && (
            <motion.div key="sent" {...slide} className="mt-8 text-center">
              <svg viewBox="0 0 52 52" className="mx-auto size-16 text-green" aria-hidden>
                <motion.circle
                  cx="26"
                  cy="26"
                  r="24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.6, ease: EASE }}
                />
                <motion.path
                  d="M15 27l7 7 15-15"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.4, ease: EASE, delay: 0.45 }}
                />
              </svg>
              <h2 id="ask-title" className="mt-5 text-2xl font-semibold tracking-[-0.03em]">
                Вопрос отправлен
              </h2>
              <p className="mt-2 text-sm text-muted">
                Ответим на <span className="font-medium text-ink">{email.trim()}</span>.
              </p>
              <button type="button" onClick={onClose} className={buttonClass("solid", "md", "mt-7 w-full")}>
                Закрыть
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
