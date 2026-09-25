import type { Metadata } from "next";
import { CheckoutResult } from "@/components/student/checkout-result";

export const metadata: Metadata = { title: "Оплата" };

export default function CheckoutSuccessPage() {
  return <CheckoutResult kind="success" />;
}
