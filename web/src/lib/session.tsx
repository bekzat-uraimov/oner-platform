"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "./api/catalog";
import { api, type RequestOptions } from "./api/client";
import type { components } from "./api/schema";

export type User = components["schemas"]["UserRead"];
type Tokens = components["schemas"]["Token"];
type OwnedCourse = components["schemas"]["CourseListItem"];

// For now both tokens live in sessionStorage: a reload keeps you signed in,
// closing the tab signs you out. Before launch the refresh token moves to an
// httpOnly cookie, out of reach of page scripts (see ONER_Frontend_TODO.md).
const KEY = "oner-session";

function load(): Tokens | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Tokens) : null;
  } catch {
    return null;
  }
}

function save(tokens: Tokens | null) {
  try {
    if (tokens) sessionStorage.setItem(KEY, JSON.stringify(tokens));
    else sessionStorage.removeItem(KEY);
  } catch {
    // Storage blocked: the session lasts until reload.
  }
}

/** Calls with the access token, renewing it once if it has expired (it lives 15 minutes). */
async function withFreshToken<T>(tokens: Tokens, call: (access: string) => Promise<T>): Promise<[T, Tokens]> {
  try {
    return [await call(tokens.access_token), tokens];
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 401) throw e;
    const renewed = await api<Tokens>("/auth/refresh", {
      method: "POST",
      json: { refresh_token: tokens.refresh_token },
    });
    return [await call(renewed.access_token), renewed];
  }
}

/** A request as the signed-in user. */
async function authed<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const tokens = load();
  if (!tokens) throw new ApiError(401, "Войдите в аккаунт", null);
  const [result, current] = await withFreshToken(tokens, (access) => api<T>(path, { ...options, token: access }));
  if (current !== tokens) save(current);
  return result;
}

type Account = { user: User; courses: OwnedCourse[] };

async function loadAccount(): Promise<Account> {
  const user = await authed<User>("/auth/me");
  const courses = await authed<OwnedCourse[]>("/me/courses");
  return { user, courses };
}

/** The account from a session left in this tab, or null. A dead session is cleared. */
async function restore(): Promise<Account | null> {
  if (!load()) return null;
  try {
    return await loadAccount();
  } catch {
    save(null);
    return null;
  }
}

type Session = {
  user: User | null;
  /** Courses the user owns; null when signed out. */
  courses: OwnedCourse[] | null;
  ready: boolean;
  owns: (courseId: number) => boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
  refreshCourses: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession needs a SessionProvider above it");
  return session;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    restore().then((restored) => {
      if (cancelled) return;
      setAccount(restored);
      setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const logout = useCallback(() => {
    save(null);
    setAccount(null);
  }, []);

  const request = useCallback(
    async <T,>(path: string, options?: RequestOptions): Promise<T> => {
      try {
        return await authed<T>(path, options);
      } catch (e) {
        // A dead session or a disabled account ends the session here too.
        if (e instanceof ApiError && (e.status === 401 || e.message === "Account disabled")) logout();
        throw e;
      }
    },
    [logout],
  );

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api<Tokens>("/auth/login", {
      method: "POST",
      form: { username: email.trim(), password },
    });
    save(tokens);
    setAccount(await loadAccount());
  }, []);

  const register = useCallback(
    async (email: string, password: string) => {
      await api("/auth/register", { method: "POST", json: { email: email.trim(), password } });
      await login(email, password);
    },
    [login],
  );

  const refreshCourses = useCallback(async () => {
    const courses = await request<OwnedCourse[]>("/me/courses");
    setAccount((current) => (current ? { ...current, courses } : current));
  }, [request]);

  const value = useMemo<Session>(
    () => ({
      user: account?.user ?? null,
      courses: account?.courses ?? null,
      ready,
      owns: (courseId) => Boolean(account?.courses.some((course) => course.id === courseId)),
      login,
      register,
      logout,
      request,
      refreshCourses,
    }),
    [account, ready, login, register, logout, request, refreshCourses],
  );
  return <SessionContext value={value}>{children}</SessionContext>;
}
