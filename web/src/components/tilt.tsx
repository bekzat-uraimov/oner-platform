"use client";

import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import type { PointerEvent, ReactNode } from "react";

const SPRING = { stiffness: 220, damping: 22, mass: 0.6 };

/** Leans toward the mouse and lights up under it. Touch and reduced motion get a still card. */
export function Tilt({ children, className = "", lift = 5 }: { children: ReactNode; className?: string; lift?: number }) {
  const reduce = useReducedMotion();
  const rotateX = useSpring(0, SPRING);
  const rotateY = useSpring(0, SPRING);
  const y = useSpring(0, SPRING);
  const mx = useMotionValue(50);
  const my = useMotionValue(50);
  const light = useMotionTemplate`radial-gradient(320px circle at ${mx}% ${my}%, color-mix(in srgb, var(--accent) 18%, transparent), transparent 62%)`;

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    mx.set(px * 100);
    my.set(py * 100);
    rotateY.set((px - 0.5) * 7);
    rotateX.set((0.5 - py) * 5);
    y.set(-lift);
  }

  function onPointerLeave() {
    rotateX.set(0);
    rotateY.set(0);
    y.set(0);
  }

  return (
    <div className="h-full [perspective:1500px]">
      <motion.div
        onPointerMove={onPointerMove}
        onPointerLeave={onPointerLeave}
        style={{ rotateX, rotateY, y }}
        className={`group/tilt relative h-full will-change-transform ${className}`}
      >
        {children}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-[6] rounded-[inherit] opacity-0 transition-opacity duration-500 group-hover/tilt:opacity-100 motion-reduce:hidden"
          style={{ backgroundImage: light }}
        />
      </motion.div>
    </div>
  );
}
