import type { Currency, PurchaseStatus } from "@/lib/api/types";

export const CURRENCIES: Currency[] = ["KGS", "KZT", "UZS", "USD"];

export const PURCHASE_STATUS: Record<PurchaseStatus, { label: string; tone: "neutral" | "green" | "red" | "amber" }> = {
  pending: { label: "Не оплачена", tone: "neutral" },
  paid: { label: "Оплачена", tone: "green" },
  failed: { label: "Ошибка оплаты", tone: "red" },
  refunded: { label: "Возврат", tone: "amber" },
};

export const PAGE_SIZE = 20;
