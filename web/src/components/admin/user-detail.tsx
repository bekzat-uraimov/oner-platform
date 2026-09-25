"use client";

import Link from "next/link";
import { useState } from "react";
import { ConfirmModal, type Confirmation } from "./confirm";
import { PurchasesTable } from "./purchases-table";
import { buttonClass } from "../button";
import { TrashIcon } from "../icons";
import { inputClass, selectClass } from "../input";
import { useToast } from "../toast";
import { Badge, cardClass, EmptyState, ErrorNote, Field, SectionHead, Skeleton, Switch, ToolButton } from "../ui";
import type { CourseListItem, UserAdminDetail } from "@/lib/api/types";
import { describe } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { useSession } from "@/lib/session";

function generatePassword(): string {
  const bytes = new Uint8Array(9);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_");
}

export function UserDetailAdmin({ userId }: { userId: number }) {
  const detail = useApi<UserAdminDetail>(`/admin/users/${userId}`);

  if (detail.error && !detail.data) {
    return detail.error.status === 404 ? (
      <EmptyState title="Пользователь не найден" action={<Link href="/admin/users" className={buttonClass()}>Все пользователи</Link>} />
    ) : (
      <ErrorNote error={detail.error} onRetry={detail.reload} />
    );
  }
  if (!detail.data) return <Skeleton className="h-96" />;
  return <UserBody user={detail.data} reload={detail.reload} />;
}

function UserBody({ user, reload }: { user: UserAdminDetail; reload: () => void }) {
  const { request, user: me } = useSession();
  const toast = useToast();
  const catalog = useApi<CourseListItem[]>("/courses");
  const [password, setPassword] = useState("");
  const [grantId, setGrantId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const owned = user.owned_courses ?? [];
  const grantable = (catalog.data ?? []).filter((course) => !owned.some((o) => o.course_id === course.id));

  async function patch(json: Record<string, unknown>, success: string, key: string) {
    setBusy(key);
    try {
      await request(`/admin/users/${user.id}`, { method: "PATCH", json });
      toast(success);
      reload();
    } catch (e) {
      toast(describe(e));
    } finally {
      setBusy(null);
    }
  }

  async function grant() {
    setBusy("grant");
    try {
      await request("/admin/entitlements", { method: "POST", json: { user_id: user.id, course_id: Number(grantId) } });
      toast("Курс выдан");
      setGrantId("");
      reload();
    } catch (e) {
      toast(describe(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="grid gap-8">
      <div>
        <Link href="/admin/users" className="text-sm text-muted transition-colors hover:text-ink">
          ← Все пользователи
        </Link>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className="grid size-12 place-items-center rounded-full bg-ink text-lg font-semibold uppercase text-bg">{user.email[0]}</span>
          <div className="min-w-0">
            <h1 className="truncate text-[clamp(22px,3vw,30px)] font-semibold tracking-[-0.03em]">{user.email}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted">
              {user.role === "admin" ? <Badge tone="accent">админ</Badge> : <Badge>студент</Badge>}
              {user.is_active ? <Badge tone="green">активен</Badge> : <Badge tone="red">отключён</Badge>}
              <span>с {formatDate(user.created_at)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className={cardClass}>
          <SectionHead title="Аккаунт" />
          <div className="grid gap-5">
            <Field label="Роль">
              <select
                value={user.role}
                disabled={busy === "role"}
                onChange={(e) => {
                  const role = e.target.value;
                  setConfirmation({
                    title: role === "admin" ? "Сделать администратором?" : "Убрать права администратора?",
                    text:
                      role === "admin"
                        ? `${user.email} получит доступ к админ-панели: курсы, пользователи, оплаты.`
                        : `${user.email} потеряет доступ к админ-панели.${user.id === me?.id ? " Это ваш аккаунт." : ""}`,
                    action: role === "admin" ? "Сделать админом" : "Убрать права",
                    run: () => patch({ role }, "Роль изменена", "role"),
                  });
                }}
                className={`${selectClass} max-w-[240px]`}
              >
                <option value="student">Студент</option>
                <option value="admin">Администратор</option>
              </select>
            </Field>
            <div className="flex items-center justify-between gap-4 rounded-card border border-line p-4">
              <div>
                <p className="text-sm font-medium">Доступ к аккаунту</p>
                <p className="mt-0.5 text-xs text-muted">Отключённый аккаунт сразу теряет вход, видео и материалы.</p>
              </div>
              <Switch
                label="Аккаунт активен"
                checked={user.is_active}
                disabled={busy === "active"}
                onChange={(active) =>
                  active
                    ? patch({ is_active: true }, "Аккаунт включён", "active")
                    : setConfirmation({
                        title: "Отключить аккаунт?",
                        text: `${user.email} больше не сможет войти, смотреть уроки и скачивать материалы. Покупки сохранятся.`,
                        action: "Отключить",
                        run: () => patch({ is_active: false }, "Аккаунт отключён", "active"),
                      })
                }
              />
            </div>
            <Field label="Новый пароль" hint="от 8 символов">
              <span className="flex flex-wrap gap-2">
                <input value={password} onChange={(e) => setPassword(e.target.value)} className={`${inputClass} min-w-0 flex-1 font-mono`} />
                <button type="button" onClick={() => setPassword(generatePassword())} className={buttonClass("line")}>
                  Сгенерировать
                </button>
              </span>
            </Field>
            <button
              type="button"
              disabled={password.length < 8 || busy === "password"}
              onClick={() => patch({ password }, "Пароль задан. Передайте его пользователю лично.", "password")}
              className={buttonClass("solid", "md", "justify-self-start disabled:opacity-40")}
            >
              Задать пароль
            </button>
          </div>
        </section>

        <section className={cardClass}>
          <SectionHead title="Курсы" hint={owned.length ? undefined : "Пока ничего не куплено и не выдано."} />
          {owned.length > 0 && (
            <ul className="grid gap-2">
              {owned.map((course) => (
                <li key={course.course_id} className="flex items-center gap-3 rounded-card border border-line p-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{course.course_title}</span>
                    <span className="text-xs text-muted">
                      {course.source_purchase_id ? `покупка #${course.source_purchase_id}` : "выдан вручную"} · {formatDate(course.granted_at)}
                    </span>
                  </span>
                  <ToolButton
                    label="Забрать курс"
                    danger
                    onClick={() =>
                      setConfirmation({
                        title: `Забрать «${course.course_title}»?`,
                        text: "Уроки и материалы закроются сразу. История оплат не меняется.",
                        action: "Забрать курс",
                        run: async () => {
                          await request(`/admin/entitlements?user_id=${user.id}&course_id=${course.course_id}`, { method: "DELETE" });
                          toast("Доступ забран");
                          reload();
                        },
                      })
                    }
                  >
                    <TrashIcon className="size-3.5" />
                  </ToolButton>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
            <select value={grantId} onChange={(e) => setGrantId(e.target.value)} aria-label="Курс для выдачи" className={`${selectClass} min-w-0 flex-1`}>
              <option value="">Выдать курс вручную…</option>
              {grantable.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                  {course.status === "draft" ? " (черновик)" : ""}
                </option>
              ))}
            </select>
            <button type="button" disabled={!grantId || busy === "grant"} onClick={grant} className={buttonClass("solid", "md", "disabled:opacity-40")}>
              Выдать
            </button>
          </div>
        </section>
      </div>

      <section>
        <SectionHead title="Оплаты" hint="Все попытки: успешные, брошенные и возвраты." />
        <PurchasesTable items={user.purchases ?? []} onChange={reload} showUser={false} />
      </section>

      <ConfirmModal confirmation={confirmation} onClose={() => setConfirmation(null)} />
    </div>
  );
}
