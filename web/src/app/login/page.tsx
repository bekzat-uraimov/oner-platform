import type { Metadata } from "next";
import { AuthScreen } from "@/components/auth/auth-screen";

export const metadata: Metadata = { title: "Вход" };

/** Only same-site paths, so a crafted link can't send someone elsewhere after sign-in. */
function safeNext(value: string | string[] | undefined): string {
  return typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\")
    ? value
    : "/";
}

export default async function LoginPage(props: PageProps<"/login">) {
  const params = await props.searchParams;
  return <AuthScreen initialMode={params.mode === "register" ? "register" : "login"} next={safeNext(params.next)} />;
}
