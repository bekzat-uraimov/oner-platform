import Link from "next/link";
import { YouTubeIcon } from "./icons";
import { Logo } from "./logo";
import { YOUTUBE_URL } from "@/lib/site";

const YEAR = new Date().getFullYear();

export function Footer() {
  return (
    <footer className="border-t border-line pb-[58px] pt-11">
      <div className="wrap">
        <div className="grid gap-[30px] md:grid-cols-[1.5fr_1fr_1fr]">
          <div>
            <Link href="/">
              <Logo className="text-[20px]" />
            </Link>
            <p className="mt-3 max-w-[30ch] text-[13.5px] leading-relaxed text-muted">
              Видеокурсы для Центральной Азии. Бишкек, Кыргызстан.
            </p>
          </div>
          <div>
            <h5 className="mb-[13px] text-[12.5px] font-medium text-muted">Платформа</h5>
            <ul className="flex flex-col gap-[9px] text-sm text-ink-2">
              <li>
                <Link href="/#courses" className="transition-colors hover:text-ink">
                  Каталог
                </Link>
              </li>
              <li>
                <Link href="/#faq" className="transition-colors hover:text-ink">
                  Вопросы
                </Link>
              </li>
              <li>
                <a href={YOUTUBE_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 transition-colors hover:text-ink">
                  <YouTubeIcon className="size-4" />
                  YouTube
                </a>
              </li>
            </ul>
          </div>
          <div>
            <h5 className="mb-[13px] text-[12.5px] font-medium text-muted">Оплата</h5>
            <p className="text-sm leading-relaxed text-ink-2">Картой местного банка через FreedomPay</p>
          </div>
        </div>
        <div className="mt-10 flex flex-wrap justify-between gap-4 border-t border-line pt-[22px] text-[13px] text-muted">
          <span>© {YEAR} ONER</span>
          <span>Сделано в Бишкеке и Сиэтле</span>
        </div>
      </div>
    </footer>
  );
}
