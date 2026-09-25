// FreedomPay's redirect back doesn't reliably say which order it was, so the
// order is remembered in the tab before leaving for the payment page.
const KEY = "oner-checkout";

export type PendingCheckout = { purchaseId: number; slug: string };

export function rememberCheckout(order: PendingCheckout) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(order));
  } catch {
    // Storage blocked: the return page falls back to "check My courses".
  }
}

export function pendingCheckout(): PendingCheckout | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as PendingCheckout) : null;
  } catch {
    return null;
  }
}
