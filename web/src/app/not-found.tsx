import { ButtonLink } from "@/components/button";
import { Enter, RiseWords } from "@/components/motion";

export default function NotFound() {
  return (
    <main className="hero-glow relative isolate grid min-h-[80vh] place-items-center pt-24 text-center">
      <div className="wrap">
        <Enter>
          <p className="font-mono text-sm text-muted">404</p>
        </Enter>
        <RiseWords
          text="Такой страницы нет"
          className="mx-auto mt-4 text-[clamp(34px,5.6vw,64px)] font-semibold leading-[1.04] tracking-[-0.045em]"
        />
        <Enter delay={0.3}>
          <p className="mx-auto mt-4 max-w-[42ch] text-ink-2">Возможно, курс сняли с продажи или ссылка устарела.</p>
        </Enter>
        <Enter delay={0.4}>
          <ButtonLink href="/#courses" className="mt-8">
            В каталог
          </ButtonLink>
        </Enter>
      </div>
    </main>
  );
}
