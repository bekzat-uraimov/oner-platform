import type { Metadata } from "next";
import { CheckoutResult } from "@/components/student/checkout-result";

export const metadata: Metadata = { title: "Оплата не прошла" };

export default function CheckoutFailurePage() {
  return <CheckoutResult kind="failure" />;
}
