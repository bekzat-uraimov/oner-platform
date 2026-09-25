"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PAGE_SIZE } from "./constants";
import { ArrowIcon } from "../icons";
import { inputClass } from "../input";
import { Badge, EmptyState, ErrorNote, PageHead, Pager, Skeleton } from "../ui";
import type { UserPage } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useApi } from "@/lib/use-api";

export function UsersAdmin() {
  const [email, setEmail] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(email.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [email]);

  const query = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (search) query.set("email", search);
  const page = useApi<UserPage>(`/admin/users?${query}`);

  return (
    <div>
      <PageHead title="Пользователи" count={page.data?.total} />
      <input
        type="search"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Поиск по почте"
        aria-label="Поиск по почте"
        className={`${inputClass} mb-5 max-w-[380px]`}
      />
      {page.error && <ErrorNote error={page.error} onRetry={page.reload} />}
      {!page.data ? (
        !page.error && <Skeleton className="h-72" />
      ) : page.data.items.length === 0 ? (
        <EmptyState title="Никого не нашли" text={search ? "Попробуйте часть почты, например домен." : "Пользователей пока нет."} />
      ) : (
        <>
          <ul className="overflow-hidden rounded-[18px] border border-line">
            {page.data.items.map((user) => (
              <li key={user.id} className="border-b border-line last:border-b-0">
                <Link href={`/admin/users/${user.id}`} className="group flex flex-wrap items-center gap-3 px-4 py-3.5 transition-colors hover:bg-surface">
                  <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-2 text-sm font-semibold uppercase text-ink-2">
                    {user.email[0]}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{user.email}</span>
                    <span className="text-xs text-muted">с {formatDate(user.created_at)}</span>
                  </span>
                  {user.role === "admin" && <Badge tone="accent">админ</Badge>}
                  {!user.is_active && <Badge tone="red">отключён</Badge>}
                  <ArrowIcon className="size-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-ink" />
                </Link>
              </li>
            ))}
          </ul>
          <Pager total={page.data.total} offset={offset} limit={PAGE_SIZE} onChange={setOffset} />
        </>
      )}
    </div>
  );
}
