import { API_URL, ApiError } from "./catalog";

export type RequestOptions = {
  method?: string;
  token?: string | null;
  json?: unknown;
  form?: Record<string, string>;
};

/** A call from the browser. Every failure becomes an ApiError; status 0 means no answer at all. */
export async function api<T>(path: string, { method = "GET", token, json, form }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = new URLSearchParams(form);
  }
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method, headers, body });
  } catch {
    throw new ApiError(0, "Сервер не отвечает. Проверьте интернет и попробуйте ещё раз.", null);
  }

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail;
    } catch {
      // Not JSON: keep the status text.
    }
    const message = typeof detail === "string" ? detail : "Проверьте заполненные поля.";
    throw new ApiError(res.status, message, res.headers.get("x-request-id"));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
