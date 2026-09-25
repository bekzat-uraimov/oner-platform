"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "./session";

/** Sends guests to sign in and back. `allowed` is true once the right user is known. */
export function useRequireUser({ admin = false }: { admin?: boolean } = {}) {
  const { user, ready } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ready && !user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [ready, user, router, pathname]);

  return { user, ready, allowed: ready && Boolean(user) && (!admin || user?.role === "admin") };
}
