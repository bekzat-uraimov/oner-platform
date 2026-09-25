"use client";

import { useEffect, useState } from "react";
import { PAGE_SIZE, PURCHASE_STATUS } from "./constants";
import { PurchasesTable } from "./purchases-table";
import { inputClass, selectClass } from "../input";
import { ErrorNote, PageHead, Pager, Skeleton } from "../ui";
import type { PurchasePage } from "@/lib/api/types";
import { useApi } from "@/lib/use-api";

export function PurchasesAdmin() {
  const [email, setEmail] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
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
  if (status) query.set("status", status);
  const page = useApi<PurchasePage>(`/admin/purchases?${query}`);

  return (
    <div>
      <PageHead title="Оплаты" count={page.data?.total} />
      <div className="mb-5 flex flex-wrap gap-3">
        <input
          type="search"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Поиск по почте покупателя"
          aria-label="Поиск по почте"
          className={`${inputClass} max-w-[340px]`}
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
          aria-label="Статус"
          className={`${selectClass} max-w-[220px]`}
        >
          <option value="">Все статусы</option>
          {Object.entries(PURCHASE_STATUS).map(([value, { label }]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      {page.error && <ErrorNote error={page.error} onRetry={page.reload} />}
      {!page.data ? (
        !page.error && <Skeleton className="h-72" />
      ) : (
        <>
          <PurchasesTable items={page.data.items} onChange={page.reload} />
          <Pager total={page.data.total} offset={offset} limit={PAGE_SIZE} onChange={setOffset} />
        </>
      )}
    </div>
  );
}
