import type { ReactNode } from "react";

function AdobeMark({ letters, bg, fg }: { letters: string; bg: string; fg: string }) {
  return (
    <span
      className="grid size-5 shrink-0 place-items-center rounded-[5px] text-[9.5px] font-bold"
      style={{ background: bg, color: fg }}
    >
      {letters}
    </span>
  );
}

const TOOLS: { name: string; mark?: ReactNode; wordmark?: ReactNode }[] = [
  {
    name: "DaVinci Resolve",
    mark: (
      <svg viewBox="0 0 24 24" className="size-5 shrink-0">
        <circle cx="12" cy="12" r="10" fill="#1d1d1f" />
        <circle cx="12" cy="12" r="5.6" fill="none" stroke="#fff" strokeWidth="1.3" />
        <circle cx="12" cy="7.4" r="1.5" fill="#ff5a5a" />
        <circle cx="16" cy="14.3" r="1.5" fill="#5ac8ff" />
        <circle cx="8" cy="14.3" r="1.5" fill="#7ee081" />
      </svg>
    ),
  },
  { name: "Premiere Pro", mark: <AdobeMark letters="Pr" bg="#2a0634" fg="#9999ff" /> },
  { name: "After Effects", mark: <AdobeMark letters="Ae" bg="#00005b" fg="#9999ff" /> },
  {
    name: "Final Cut Pro",
    mark: (
      <svg viewBox="0 0 24 24" fill="currentColor" className="size-5 shrink-0">
        <path d="M17.05 12.54c-.02-2.3 1.88-3.4 1.96-3.46-1.07-1.56-2.73-1.78-3.32-1.8-1.42-.14-2.77.83-3.49.83-.72 0-1.83-.81-3-.79-1.55.02-2.97.9-3.77 2.28-1.6 2.79-.41 6.92 1.15 9.18.76 1.11 1.67 2.35 2.86 2.3 1.15-.04 1.58-.74 2.97-.74 1.39 0 1.78.74 3 .72 1.24-.02 2.02-1.12 2.78-2.24.87-1.28 1.23-2.53 1.25-2.59-.03-.01-2.4-.92-2.42-3.65M14.9 5.2c.63-.77 1.06-1.83.94-2.9-.91.04-2.02.61-2.67 1.37-.58.68-1.09 1.77-.95 2.81 1.02.08 2.05-.52 2.68-1.28" />
      </svg>
    ),
  },
  { name: "Lightroom", mark: <AdobeMark letters="Lr" bg="#001e36" fg="#31a8ff" /> },
  {
    name: "Instagram",
    mark: (
      <svg viewBox="0 0 24 24" className="size-5 shrink-0">
        <defs>
          <linearGradient id="ig-gradient" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#feda75" />
            <stop offset=".5" stopColor="#d62976" />
            <stop offset="1" stopColor="#4f5bd5" />
          </linearGradient>
        </defs>
        <rect x="3" y="3" width="18" height="18" rx="5.5" fill="none" stroke="url(#ig-gradient)" strokeWidth="2.2" />
        <circle cx="12" cy="12" r="4.2" fill="none" stroke="url(#ig-gradient)" strokeWidth="2.2" />
        <circle cx="17.3" cy="6.7" r="1.3" fill="url(#ig-gradient)" />
      </svg>
    ),
  },
  {
    name: "YouTube",
    mark: (
      <svg viewBox="0 0 24 24" className="size-5 shrink-0">
        <rect x="1.5" y="5" width="21" height="14" rx="4.5" fill="#ff0033" />
        <path d="M10 9v6l5.2-3z" fill="#fff" />
      </svg>
    ),
  },
  { name: "Sony", wordmark: <span className="text-sm font-bold tracking-[0.16em] text-ink">SONY</span> },
  { name: "Canon", wordmark: <span className="font-serif text-[15px] font-bold tracking-tight text-[#cc0000]">Canon</span> },
];

function Tool({ tool, copy }: { tool: (typeof TOOLS)[number]; copy: boolean }) {
  return (
    <span
      aria-hidden={copy || undefined}
      className="inline-flex shrink-0 items-center gap-[9px] rounded-xl border border-line bg-bg px-[17px] py-[11px] text-sm font-medium text-ink-2 opacity-70 grayscale transition-[filter,opacity,transform,border-color,box-shadow] duration-500 ease-out-expo hover:-translate-y-[3px] hover:border-line-strong hover:opacity-100 hover:shadow-lift hover:grayscale-0"
    >
      {tool.wordmark ?? (
        <>
          {tool.mark}
          {tool.name}
        </>
      )}
    </span>
  );
}

/** The tools and platforms the courses teach, sliding past like Mobbin's logo row. */
export function ToolLogos() {
  return (
    <div className="mt-14 border-t border-line pt-11">
      <p className="mb-7 text-center text-[13px] font-medium text-muted">Инструменты и площадки, с которыми работаем</p>
      <div className="marquee relative overflow-hidden py-1 [mask-image:linear-gradient(90deg,transparent,#000_12%,#000_88%,transparent)]">
        <ul aria-label="Инструменты" className="marquee-track flex w-max gap-3.5 pr-3.5">
          {[...TOOLS, ...TOOLS].map((tool, i) => (
            <li key={`${tool.name}-${i}`} className="flex">
              <Tool tool={tool} copy={i >= TOOLS.length} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
