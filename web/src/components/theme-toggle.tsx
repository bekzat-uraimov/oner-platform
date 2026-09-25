"use client";

import { motion } from "motion/react";
import { useLayoutEffect } from "react";
import { MoonIcon, SunIcon } from "./icons";

export const THEME_KEY = "oner-theme";

function preferred(): string {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) return saved;
  } catch {
    // Storage blocked: fall back to the system setting.
  }
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  // The inline script in the layout sets the theme before paint. React's
  // development remount clears it, so set it again; in production this is a no-op.
  useLayoutEffect(() => {
    document.documentElement.setAttribute("data-theme", preferred());
  }, []);

  function toggle() {
    const root = document.documentElement;
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage blocked: the choice lasts until reload.
    }
  }

  return (
    <motion.button
      type="button"
      onClick={toggle}
      whileTap={{ scale: 0.88, rotate: 25 }}
      aria-label="Сменить тему"
      className="grid size-9 place-items-center rounded-full border border-line text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
    >
      <MoonIcon className="size-4 dark:hidden" />
      <SunIcon className="hidden size-4 dark:block" />
    </motion.button>
  );
}
