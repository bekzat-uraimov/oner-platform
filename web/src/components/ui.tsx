"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { buttonClass } from "./button";
import { PlusIcon } from "./icons";
import type { ApiError } from "@/lib/api/catalog";
import { errorText } from "@/lib/errors";
import { EASE } from "@/lib/motion";

const subscribeNothing = () => () => {};

/** False during server rendering and hydration, true after. For things that need `document`. */
export function useIsClient(): boolean {
  return useSyncExternalStore(subscribeNothing, () => true, () => false);
}

export const cardClass = "rounded-[18px] border border-line bg-bg p-5 sm:p-6";

export function Spinner({ className = "size-4" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Загрузка"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

/** The deck's section label: "01 — Каталог". */
export function Eyebrow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`font-mono text-[11px] uppercase tracking-[0.24em] text-brand ${className}`}>{children}</p>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-card bg-surface-2 ${className}`} />;
}

export function EmptyState({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="rounded-[18px] border border-dashed border-line-strong px-6 py-14 text-center">
      <p className="text-lg font-semibold tracking-[-0.02em]">{title}</p>
      {text && <p className="mx-auto mt-2 max-w-[46ch] text-sm leading-relaxed text-muted">{text}</p>}
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: ApiError | string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#f3c4c0] bg-[#fff3f2] px-4 py-3 text-sm text-[#b42318] dark:border-[#4a2020] dark:bg-[#231111] dark:text-[#ff9a8f]"
    >
      <span>{typeof error === "string" ? error : errorText(error)}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-medium underline underline-offset-4">
          Повторить
        </button>
      )}
    </div>
  );
}

const TONES = {
  neutral: "border-line bg-surface text-ink-2",
  green: "border-transparent bg-green/12 text-green",
  amber: "border-transparent bg-[#f59e0b]/15 text-[#b45309] dark:text-[#fbbf24]",
  red: "border-transparent bg-[#ef4444]/12 text-[#b42318] dark:text-[#ff8a80]",
  accent: "border-transparent bg-accent/12 text-accent",
  brand: "border-transparent bg-brand/15 text-ink dark:text-brand",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: keyof typeof TONES }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function Field({
  label,
  hint,
  error,
  className = "",
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  className?: string;
  children: ReactNode;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-2 flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">{label}</span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </span>
      {children}
      {error && <span className="mt-1.5 block text-xs text-[#b42318] dark:text-[#ff9a8f]">{error}</span>}
    </label>
  );
}

export function PageHead({ title, count, action }: { title: string; count?: number; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-baseline gap-3">
        <h1 className="text-[clamp(24px,3vw,32px)] font-semibold tracking-[-0.035em]">{title}</h1>
        {count !== undefined && <span className="font-mono text-sm text-muted">{count}</span>}
      </div>
      {action}
    </div>
  );
}

export function SectionHead({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-xl font-semibold tracking-[-0.025em]">{title}</h2>
        {hint && <p className="mt-1 text-sm text-muted">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

export function ToolButton({
  label,
  onClick,
  disabled,
  danger = false,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className={`grid size-8 shrink-0 place-items-center rounded-full border border-line text-muted transition-colors hover:bg-surface-2 disabled:pointer-events-none disabled:opacity-30 ${
        danger ? "hover:border-[#f3c4c0] hover:text-[#b42318] dark:hover:border-[#4a2020] dark:hover:text-[#ff8a80]" : "hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative flex h-6 w-11 shrink-0 items-center rounded-full px-0.5 transition-colors duration-300 disabled:opacity-50 ${
        checked ? "justify-end bg-green" : "justify-start bg-line-strong"
      }`}
    >
      <motion.span layout transition={{ type: "spring", stiffness: 500, damping: 34 }} className="size-5 rounded-full bg-white shadow" />
    </button>
  );
}

export function Pager({
  total,
  offset,
  limit,
  onChange,
}: {
  total: number;
  offset: number;
  limit: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  return (
    <div className="mt-5 flex items-center justify-between text-sm text-muted">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} из {total}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className={buttonClass("line", "sm", "disabled:opacity-40")}
        >
          Назад
        </button>
        <button
          type="button"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
          className={buttonClass("line", "sm", "disabled:opacity-40")}
        >
          Дальше
        </button>
      </div>
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  width = "max-w-[520px]",
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  width?: string;
  children: ReactNode;
}) {
  const isClient = useIsClient();
  if (!isClient) return null;
  return createPortal(
    <AnimatePresence>
      {open && (
        <ModalFrame key="modal" onClose={onClose} title={title} width={width}>
          {children}
        </ModalFrame>
      )}
    </AnimatePresence>,
    document.body,
  );
}

function ModalFrame({
  onClose,
  title,
  width,
  children,
}: {
  onClose: () => void;
  title: string;
  width: string;
  children: ReactNode;
}) {
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

  return (
    <motion.div
      className="fixed inset-0 z-[400] flex items-end justify-center p-3 sm:items-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div aria-hidden onClick={onClose} className="absolute inset-0 bg-black/45 backdrop-blur-sm" />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        initial={{ y: 32, scale: 0.97, opacity: 0 }}
        animate={{ y: 0, scale: 1, opacity: 1 }}
        exit={{ y: 20, scale: 0.98, opacity: 0 }}
        transition={{ duration: 0.45, ease: EASE }}
        className={`relative flex max-h-[90vh] w-full flex-col overflow-hidden rounded-[22px] border border-line bg-bg shadow-float ${width}`}
      >
        <div className="flex items-center justify-between gap-4 border-b border-line px-6 py-4">
          <h2 className="text-lg font-semibold tracking-[-0.02em]">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="grid size-8 place-items-center rounded-full border border-line text-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <PlusIcon className="size-3.5 rotate-45" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
      </motion.div>
    </motion.div>
  );
}
