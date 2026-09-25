"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ButtonLink } from "./button";
import { YouTubeIcon } from "./icons";
import { Logo } from "./logo";
import { Magnetic } from "./motion";
import { ThemeToggle } from "./theme-toggle";
import { EASE } from "@/lib/motion";
import { useSession, type User } from "@/lib/session";
import { YOUTUBE_URL } from "@/lib/site";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const { user, ready, logout } = useSession();
  const pathname = usePathname();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = [
    ["/#courses", "Курсы"],
    ["/#faq", "Вопросы"],
    ...(user ? [["/me", "Мои курсы"] as const] : []),
  ] as const;

  return (
    <div className="pointer-events-none fixed inset-x-0 top-[18px] z-[100] flex justify-center px-4">
      <motion.nav
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.8, ease: EASE }}
        className={`pointer-events-auto flex w-full max-w-[1000px] items-center gap-2 rounded-full border bg-bg/75 py-2 pl-5 pr-2 backdrop-blur-xl backdrop-saturate-[1.8] transition-[box-shadow,border-color] duration-300 ${
          scrolled ? "border-line-strong shadow-lift" : "border-line shadow-soft"
        }`}
      >
        <Link href="/" aria-label="ONER — на главную" className="shrink-0 text-[17px]">
          <Logo />
        </Link>
        <div className="ml-4 flex gap-0.5 max-md:hidden">
          {links.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              className={`rounded-full px-3 py-[7px] text-sm font-medium transition-colors hover:bg-surface-2 hover:text-ink ${
                pathname === href ? "text-ink" : "text-ink-2"
              }`}
            >
              {label}
            </Link>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <a
            href={YOUTUBE_URL}
            target="_blank"
            rel="noreferrer"
            aria-label="ONER на YouTube"
            className="grid size-9 place-items-center rounded-full border border-line transition-colors hover:bg-surface-2"
          >
            <YouTubeIcon className="size-[18px]" />
          </a>
          <ThemeToggle />
          <AnimatePresence mode="wait" initial={false}>
            {ready && (
              <motion.div
                key={user ? "account" : "guest"}
                initial={{ opacity: 0, scale: 0.94 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.94 }}
                transition={{ duration: 0.3, ease: EASE }}
              >
                {user ? (
                  <AccountMenu user={user} onLogout={logout} />
                ) : pathname !== "/login" ? (
                  <ButtonLink href={`/login?next=${encodeURIComponent(pathname)}`} variant="line" size="sm">
                    Войти
                  </ButtonLink>
                ) : null}
              </motion.div>
            )}
          </AnimatePresence>
          <Magnetic className="max-sm:hidden">
            <ButtonLink href="/#courses" size="sm">
              Смотреть курсы
            </ButtonLink>
          </Magnetic>
        </div>
      </motion.nav>
    </div>
  );
}

function AccountMenu({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!menu.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const item = "block w-full rounded-xl px-3 py-2.5 text-left text-sm text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink";

  return (
    <div ref={menu} className="relative">
      <button
        type="button"
        aria-label="Аккаунт"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((isOpen) => !isOpen)}
        className="grid size-9 place-items-center rounded-full bg-ink text-sm font-semibold uppercase text-bg transition-transform active:scale-95"
      >
        {user.email[0]}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            initial={{ opacity: 0, y: -6, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.96 }}
            transition={{ duration: 0.25, ease: EASE }}
            className="absolute right-0 top-12 w-64 origin-top-right rounded-2xl border border-line bg-bg p-2 shadow-float"
          >
            <p className="px-3 pt-1.5 text-xs text-muted">Вы вошли как</p>
            <p className="truncate px-3 pb-3 pt-0.5 text-sm font-medium">{user.email}</p>
            <div className="h-px bg-line" />
            <div className="mt-1" onClick={() => setOpen(false)}>
              <Link role="menuitem" href="/me" className={item}>
                Мои курсы
              </Link>
              {user.role === "admin" && (
                <Link role="menuitem" href="/admin/courses" className={item}>
                  Админ-панель
                </Link>
              )}
              <button type="button" role="menuitem" onClick={onLogout} className={item}>
                Выйти
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
