"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";
import { ToastProvider } from "./toast";
import { SessionProvider } from "@/lib/session";

export function Providers({ children }: { children: ReactNode }) {
  // "user" follows the OS reduced-motion setting: movement off, fades kept.
  return (
    <MotionConfig reducedMotion="user">
      <SessionProvider>
        <ToastProvider>{children}</ToastProvider>
      </SessionProvider>
    </MotionConfig>
  );
}
