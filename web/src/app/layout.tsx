import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Footer } from "@/components/footer";
import { Nav } from "@/components/nav";
import { Providers } from "@/components/providers";
import { ScrollProgress } from "@/components/scroll-progress";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin", "cyrillic"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  title: { default: "ONER — курсы от практиков Центральной Азии", template: "%s — ONER" },
  description:
    "Премиальные видеокурсы по съёмке, свету, монтажу, цвету и режиссуре от профессионалов Центральной Азии.",
};

// Runs while the HTML is parsed, before first paint: the saved theme, else the
// system's. Without it a dark-mode visitor sees a white flash.
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("oner-theme");if(!t)t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" data-theme="light" suppressHydrationWarning className={`${inter.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <Providers>
          <ScrollProgress />
          <Nav />
          {children}
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
