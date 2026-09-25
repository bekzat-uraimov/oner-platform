import Link from "next/link";
import type { ComponentProps } from "react";

const BASE =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium transition-[opacity,background-color,box-shadow,transform] duration-300 ease-out-expo active:scale-[0.97]";

const VARIANTS = {
  solid: "bg-ink text-bg hover:opacity-85",
  line: "border border-line text-ink hover:bg-surface-2",
  danger: "bg-[#d92d20] text-white hover:opacity-90",
};

const SIZES = {
  md: "px-[22px] py-3 text-[15px]",
  sm: "px-[17px] py-[9px] text-sm",
};

export type ButtonVariant = keyof typeof VARIANTS;
export type ButtonSize = keyof typeof SIZES;

export function buttonClass(variant: ButtonVariant = "solid", size: ButtonSize = "md", extra = "") {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${extra}`;
}

export function ButtonLink({
  variant,
  size,
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: ButtonSize }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />;
}
