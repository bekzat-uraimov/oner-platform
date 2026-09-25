"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { PlusIcon } from "./icons";
import { Reveal } from "./motion";
import { EASE } from "@/lib/motion";

export function Faq({ items }: { items: readonly (readonly [string, string])[] }) {
  const [open, setOpen] = useState(0);

  return (
    <div className="max-w-[820px]">
      {items.map(([question, answer], i) => {
        const isOpen = open === i;
        return (
          <Reveal key={question} delay={Math.min(i * 0.05, 0.2)} className="border-b border-line">
            <h3>
              <button
                type="button"
                aria-expanded={isOpen}
                aria-controls={`faq-${i}`}
                onClick={() => setOpen(isOpen ? -1 : i)}
                className="flex w-full items-center justify-between gap-6 py-[21px] text-left text-[16.5px] font-medium transition-colors hover:text-accent"
              >
                {question}
                <motion.span
                  animate={{ rotate: isOpen ? 45 : 0 }}
                  transition={{ duration: 0.4, ease: EASE }}
                  className="grid size-7 shrink-0 place-items-center rounded-full border border-line text-muted"
                >
                  <PlusIcon className="size-3.5" />
                </motion.span>
              </button>
            </h3>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  id={`faq-${i}`}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.45, ease: EASE }}
                  className="overflow-hidden"
                >
                  <p className="pb-[22px] pr-12 text-[15px] leading-[1.68] text-ink-2">{answer}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </Reveal>
        );
      })}
    </div>
  );
}
