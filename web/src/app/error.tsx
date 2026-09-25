"use client";

import { useEffect } from "react";
import { buttonClass } from "@/components/button";

export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="hero-glow relative isolate grid min-h-[80vh] place-items-center pt-24 text-center">
      <div className="wrap">
        <h1 className="text-[clamp(30px,4.6vw,52px)] font-semibold tracking-[-0.04em]">Что-то пошло не так</h1>
        <p className="mx-auto mt-4 max-w-[42ch] text-ink-2">Сервер не ответил. Попробуйте ещё раз через минуту.</p>
        {error.digest && <p className="mt-2 font-mono text-xs text-muted">{error.digest}</p>}
        <button type="button" onClick={() => retry()} className={buttonClass("solid", "md", "mt-8")}>
          Попробовать снова
        </button>
      </div>
    </main>
  );
}
