"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api/catalog";
import { useSession } from "./session";

type Loaded<T> = { path: string; version: number; data?: T; error?: ApiError };

/**
 * GET `path` as the signed-in user. Pass null to wait. `reload` fetches again
 * and keeps showing the current data meanwhile, so lists don't flash.
 */
export function useApi<T>(path: string | null) {
  const { request } = useSession();
  const [version, setVersion] = useState(0);
  const [loaded, setLoaded] = useState<Loaded<T> | null>(null);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    request<T>(path).then(
      (data) => {
        if (!cancelled) setLoaded({ path, version, data });
      },
      (error: unknown) => {
        if (cancelled) return;
        const failure = error instanceof ApiError ? error : new ApiError(0, "Не удалось загрузить данные.", null);
        setLoaded({ path, version, error: failure });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [path, version, request]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const current = loaded && loaded.path === path ? loaded : null;

  return {
    data: current?.data,
    error: current?.version === version ? current.error : undefined,
    loading: Boolean(path) && current?.version !== version,
    reload,
  };
}
