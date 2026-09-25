"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { buttonClass, type ButtonSize } from "../button";
import { Magnetic } from "../motion";
import { useToast } from "../toast";
import { Spinner } from "../ui";
import { ApiError } from "@/lib/api/catalog";
import type { CheckoutResponse } from "@/lib/api/types";
import { rememberCheckout } from "@/lib/checkout";
import { describe } from "@/lib/errors";
import { useSession } from "@/lib/session";

export function BuyButton({
  courseId,
  slug,
  label,
  size = "md",
  className = "",
}: {
  courseId: number;
  slug: string;
  label: string;
  size?: ButtonSize;
  className?: string;
}) {
  const toast = useToast();
  const { user, owns, request, refreshCourses } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const [busy, setBusy] = useState(false);

  async function buy() {
    // Buying needs an account; send guests to sign in and bring them back here.
    if (!user) {
      router.push(`/login?next=${encodeURIComponent(pathname)}`);
      return;
    }
    setBusy(true);
    try {
      const order = await request<CheckoutResponse>("/checkout", { method: "POST", json: { course_id: courseId } });
      rememberCheckout({ purchaseId: order.purchase_id, slug });
      window.location.assign(order.redirect_url);
    } catch (e) {
      setBusy(false);
      if (e instanceof ApiError && e.status === 409) {
        await refreshCourses().catch(() => undefined);
        router.push(`/learn/${slug}`);
        return;
      }
      toast(describe(e));
    }
  }

  if (user && owns(courseId)) {
    return (
      <Magnetic className={className}>
        <Link href={`/learn/${slug}`} className={buttonClass("solid", size, "w-full")}>
          {size === "sm" ? "Учиться" : "Продолжить обучение"}
        </Link>
      </Magnetic>
    );
  }

  return (
    <Magnetic className={className}>
      <button type="button" onClick={buy} disabled={busy} className={buttonClass("solid", size, "w-full disabled:opacity-70")}>
        {busy ? <Spinner /> : label}
      </button>
    </Magnetic>
  );
}
