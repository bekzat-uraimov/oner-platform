"use client";

import { animate, motion, useInView, useReducedMotion, useSpring } from "motion/react";
import { Fragment, useEffect, useRef, type PointerEvent, type ReactNode } from "react";
import { EASE } from "@/lib/motion";

type Wrapper = { children: ReactNode; className?: string; delay?: number };

/** Rises in, sharpening from a blur, the first time it scrolls into view. */
export function Reveal({ children, className, delay = 0, as = "div" }: Wrapper & { as?: "div" | "li" }) {
  const Tag = as === "li" ? motion.li : motion.div;
  return (
    <Tag
      className={className}
      initial={{ opacity: 0, y: 22, filter: "blur(7px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "0px 0px -60px 0px" }}
      transition={{ duration: 0.85, ease: EASE, delay }}
    >
      {children}
    </Tag>
  );
}

/** Rises in on page load, for what's above the fold. */
export function Enter({ children, className, delay = 0 }: Wrapper) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.9, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/** A headline whose words rise one by one from behind a mask. `accent` is a tail, like a final dot, in the brand colour. */
export function RiseWords({
  text,
  className,
  delay = 0.12,
  accent,
}: {
  text: string;
  className?: string;
  delay?: number;
  accent?: string;
}) {
  const words = text.split(" ");
  return (
    <h1 className={className} aria-label={accent ? text + accent : text}>
      {words.map((word, i) => (
        <Fragment key={i}>
          <span aria-hidden className="-mb-[0.08em] inline-block overflow-hidden pb-[0.08em] align-bottom">
            <motion.span
              className="inline-block"
              initial={{ y: "115%" }}
              animate={{ y: 0 }}
              transition={{ duration: 1, ease: EASE, delay: delay + i * 0.06 }}
            >
              {word}
              {accent && i === words.length - 1 ? <span className="text-brand">{accent}</span> : null}
            </motion.span>
          </span>
          {i < words.length - 1 ? " " : null}
        </Fragment>
      ))}
    </h1>
  );
}

const MAGNET = { stiffness: 260, damping: 18, mass: 0.4 };

/** Drifts toward the mouse while it hovers. Touch and reduced motion leave it still. */
export function Magnetic({ children, className = "" }: { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  const x = useSpring(0, MAGNET);
  const y = useSpring(0, MAGNET);

  function onPointerMove(e: PointerEvent<HTMLSpanElement>) {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - (r.left + r.width / 2)) * 0.22);
    y.set((e.clientY - (r.top + r.height / 2)) * 0.32);
  }

  function onPointerLeave() {
    x.set(0);
    y.set(0);
  }

  return (
    <motion.span
      className={`inline-flex ${className}`}
      style={{ x, y }}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
    >
      {children}
    </motion.span>
  );
}

/** Counts up to a number when it comes into view. The server renders the final number. */
export function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || !inView || reduce) return;
    const controls = animate(0, to, {
      duration: 1.2,
      ease: EASE,
      onUpdate: (value) => {
        el.textContent = String(Math.round(value));
      },
    });
    return () => controls.stop();
  }, [inView, reduce, to]);

  return (
    <span ref={ref} className="font-mono tabular-nums">
      {to}
    </span>
  );
}
