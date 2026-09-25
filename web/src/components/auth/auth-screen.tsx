"use client";

import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { buttonClass } from "../button";
import { inputClass } from "../input";
import { Enter, RiseWords } from "../motion";
import { ApiError } from "@/lib/api/catalog";
import { EASE } from "@/lib/motion";
import { useSession } from "@/lib/session";

type Mode = "login" | "register";

const COPY = {
  login: { title: "С возвращением", lede: "Войдите, чтобы открыть свои курсы.", submit: "Войти" },
  register: {
    title: "Создайте аккаунт",
    lede: "Аккаунт нужен, чтобы купить курс и смотреть уроки.",
    submit: "Создать аккаунт",
  },
} as const;

function messageFor(error: unknown, mode: Mode): string {
  if (!(error instanceof ApiError)) return "Что-то пошло не так. Попробуйте ещё раз.";
  switch (error.status) {
    case 0:
      return error.message;
    case 401:
      return "Неверная почта или пароль.";
    case 403:
      return "Аккаунт отключён. Напишите в поддержку.";
    case 409:
      return "Эта почта уже зарегистрирована. Войдите в аккаунт.";
    case 422:
      return mode === "register" ? "Проверьте почту. Пароль должен быть не короче 8 символов." : "Проверьте почту и пароль.";
    case 429:
      return "Слишком много попыток. Подождите минуту.";
    default:
      return "Сервер ответил ошибкой. Попробуйте позже.";
  }
}

export function AuthScreen({ initialMode, next }: { initialMode: Mode; next: string }) {
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { user, ready, login, register, logout } = useSession();
  const router = useRouter();

  function switchTo(value: Mode) {
    setMode(value);
    setError(null);
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      router.replace(next);
    } catch (err) {
      setError(messageFor(err, mode));
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      <section className="hero-glow relative isolate flex items-center justify-center px-6 pb-16 pt-[120px]">
        <div className="w-full max-w-[400px]">
          {ready && user && !busy ? (
            <div>
              <Enter>
                <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted">Вы уже вошли</p>
              </Enter>
              <RiseWords text="Всё готово" className="mt-6 text-[clamp(32px,4vw,44px)] font-semibold tracking-[-0.04em]" />
              <Enter delay={0.2}>
                <p className="mt-3 text-[15px] text-ink-2">
                  Аккаунт: <span className="font-medium text-ink">{user.email}</span>
                </p>
              </Enter>
              <Enter delay={0.3} className="mt-8 flex flex-wrap gap-3">
                <Link href={next} className={buttonClass()}>
                  Продолжить
                </Link>
                <button type="button" onClick={logout} className={buttonClass("line")}>
                  Выйти
                </button>
              </Enter>
            </div>
          ) : (
            <>
              <Enter>
                <ModeSwitch mode={mode} onChange={switchTo} />
              </Enter>
              <RiseWords
                key={mode}
                text={COPY[mode].title}
                delay={0.05}
                className="mt-8 text-[clamp(32px,4vw,44px)] font-semibold leading-[1.05] tracking-[-0.04em]"
              />
              <Enter delay={0.12}>
                <p className="mt-3 text-[15px] text-ink-2">{COPY[mode].lede}</p>
              </Enter>
              <Enter delay={0.2}>
                <form onSubmit={onSubmit} noValidate className="mt-8 flex flex-col gap-4">
                  <Field label="Почта" htmlFor="email">
                    <input
                      id="email"
                      type="email"
                      inputMode="email"
                      autoComplete="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@mail.ru"
                      className={inputClass}
                    />
                  </Field>
                  <Field label="Пароль" htmlFor="password" hint={mode === "register" ? "Минимум 8 символов" : undefined}>
                    <div className="relative">
                      <input
                        id="password"
                        type={showPassword ? "text" : "password"}
                        autoComplete={mode === "login" ? "current-password" : "new-password"}
                        required
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className={`${inputClass} pr-24`}
                      />
                      <button
                        type="button"
                        aria-pressed={showPassword}
                        onClick={() => setShowPassword((shown) => !shown)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-surface-2 hover:text-ink"
                      >
                        {showPassword ? "Скрыть" : "Показать"}
                      </button>
                    </div>
                  </Field>
                  <AnimatePresence>
                    {error && (
                      <motion.p
                        role="alert"
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.35, ease: EASE }}
                        className="overflow-hidden"
                      >
                        <span className="block rounded-xl border border-[#f3c4c0] bg-[#fff3f2] px-4 py-3 text-sm text-[#b42318] dark:border-[#4a2020] dark:bg-[#231111] dark:text-[#ff9a8f]">
                          {error}
                        </span>
                      </motion.p>
                    )}
                  </AnimatePresence>
                  <button type="submit" disabled={busy} className={buttonClass("solid", "md", "mt-2 w-full disabled:opacity-70")}>
                    {busy ? (
                      <span aria-label="Подождите" className="size-4 animate-spin rounded-full border-2 border-bg/30 border-t-bg" />
                    ) : (
                      COPY[mode].submit
                    )}
                  </button>
                </form>
              </Enter>
              <Enter delay={0.3}>
                <p className="mt-6 text-center text-xs text-muted">Сессия живёт в этой вкладке: закроете её, и выйдете.</p>
              </Enter>
            </>
          )}
        </div>
      </section>
      <BrandPanel />
    </main>
  );
}

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <label htmlFor={htmlFor} className="text-sm font-medium">
          {label}
        </label>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <LayoutGroup id="auth-mode">
      <div role="tablist" aria-label="Вход или регистрация" className="inline-flex rounded-full border border-line p-1">
        {(["login", "register"] as const).map((option) => {
          const selected = option === mode;
          return (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(option)}
              className={`relative rounded-full px-4 py-2 text-sm font-medium transition-colors duration-300 ${
                selected ? "text-bg" : "text-muted hover:text-ink"
              }`}
            >
              {selected && (
                <motion.span
                  layoutId="auth-pill"
                  className="absolute inset-0 rounded-full bg-ink"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                />
              )}
              <span className="relative">{option === "login" ? "Вход" : "Регистрация"}</span>
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
}

const FLOATING = [
  { label: "Цвет", position: "-top-44 left-0 -rotate-[8deg]", art: "linear-gradient(125deg,#1d4ed8 0%,#7c2d6b 48%,#1a1220 100%)" },
  { label: "Свет", position: "-top-28 right-2 rotate-[7deg]", art: "linear-gradient(130deg,#9d174d,#4c1d95 58%,#140d1c)" },
  { label: "Монтаж", position: "top-40 right-20 -rotate-[4deg]", art: "linear-gradient(125deg,#0f766e 0%,#1e3a8a 52%,#0c1222 100%)" },
];

function BrandPanel() {
  return (
    <aside className="relative isolate hidden overflow-hidden bg-[#0a0a0b] text-white lg:block">
      <div aria-hidden className="auth-grid absolute inset-0 -z-10" />
      <div
        aria-hidden
        className="absolute left-1/2 top-1/2 -z-10 size-[640px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(181,242,61,.2),transparent_62%)]"
      />
      <div className="flex h-full flex-col justify-between p-12 pt-[120px]">
        <Enter delay={0.1}>
          <p className="font-mono text-[11px] uppercase tracking-[0.32em] text-[#b5f23d]">искусство · ремесло · мастерство</p>
        </Enter>
        <div className="relative">
          {FLOATING.map((card, i) => (
            <motion.div
              key={card.label}
              aria-hidden
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: [0, -14, 0] }}
              transition={{
                opacity: { duration: 0.9, delay: 0.3 + i * 0.12 },
                y: { duration: 6 + i * 1.3, repeat: Infinity, ease: "easeInOut", delay: i * 0.4 },
              }}
              className={`absolute w-44 overflow-hidden rounded-2xl border border-white/10 shadow-[0_24px_60px_rgba(0,0,0,.5)] ${card.position}`}
            >
              <div className="relative aspect-[4/3]" style={{ background: card.art }}>
                <div className="art-grain absolute inset-0" />
                <span className="absolute bottom-2 left-2 rounded-md border border-white/20 bg-black/40 px-2 py-0.5 text-[11px] font-medium backdrop-blur">
                  {card.label}
                </span>
              </div>
            </motion.div>
          ))}
          <motion.div
            initial={{ opacity: 0, scale: 0.92, filter: "blur(12px)" }}
            animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
            transition={{ duration: 1.1, ease: EASE, delay: 0.15 }}
          >
            <span className="block text-[clamp(64px,7vw,104px)] font-bold leading-none tracking-[0.12em] text-[#b5f23d]">ONER</span>
          </motion.div>
          <Enter delay={0.35}>
            <p className="mt-6 max-w-[34ch] text-[17px] leading-relaxed text-white/70">
              Премиальные видеокурсы по кино и видеопроизводству для русскоязычной Центральной Азии.
            </p>
          </Enter>
        </div>
        <Enter delay={0.45}>
          <p className="text-sm text-white/45">Искусство, ремесло, мастерство.</p>
        </Enter>
      </div>
    </aside>
  );
}
