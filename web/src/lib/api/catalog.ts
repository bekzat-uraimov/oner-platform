import type { components } from "./schema";

export type CourseListItem = components["schemas"]["CourseListItem"];
export type CourseDetail = components["schemas"]["CourseDetail"];

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  requestId: string | null;

  constructor(status: number, message: string, requestId: string | null) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}

// Catalog pages look the same for every visitor, so their data is cached for a
// minute. An admin's edit shows up within that.
async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Not JSON: keep the status text.
    }
    throw new ApiError(res.status, detail, res.headers.get("x-request-id"));
  }
  return (await res.json()) as T;
}

export function listCourses(): Promise<CourseListItem[]> {
  return get("/courses");
}

export async function getCourse(slug: string): Promise<CourseDetail | null> {
  try {
    return await get<CourseDetail>(`/courses/${encodeURIComponent(slug)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}
