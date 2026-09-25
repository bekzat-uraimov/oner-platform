"use client";

import { LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ButtonLink } from "../button";
import { EmptyState, Eyebrow, Skeleton } from "../ui";
import { EASE } from "@/lib/motion";
import { useRequireUser } from "@/lib/use-require-user";

const SECTIONS = [
  ["/admin/courses", "Курсы"],
  ["/admin/users", "Пользователи"],
  ["/admin/purchases", "Оплаты"],
  ["/admin/storage", "Хранилище"],
] as const;

export function AdminShell({ children }: { children: ReactNode }) {
  const { allowed, ready, user } = useRequireUser({ admin: true });
  const pathname = usePathname();

  if (ready && user && user.role !== "admin") {
    return (
      <main className="grid min-h-[80vh] place-items-center pt-24">
        <div className="wrap w-full max-w-[560px]">
          <EmptyState
            title="Нет доступа"
            text="Эта часть сайта только для администраторов."
            action={<ButtonLink href="/">На главную</ButtonLink>}
          />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen pb-24 pt-[108px]">
      <div className="wrap">
        <Eyebrow>Админ-панель</Eyebrow>
        <LayoutGroup id="admin-tabs">
          <nav className="mt-4 flex gap-1 overflow-x-auto border-b border-line">
            {SECTIONS.map(([href, label]) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`relative shrink-0 px-4 py-3 text-sm font-medium transition-colors ${active ? "text-ink" : "text-muted hover:text-ink"}`}
                >
                  {label}
                  {active && (
                    <motion.span
                      layoutId="admin-tab"
                      transition={{ duration: 0.35, ease: EASE }}
                      className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-ink"
                    />
                  )}
                </Link>
              );
            })}
          </nav>
        </LayoutGroup>
        <div className="mt-8">
          {allowed ? (
            children
          ) : (
            <div className="grid gap-3">
              <Skeleton className="h-12" />
              <Skeleton className="h-72" />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
