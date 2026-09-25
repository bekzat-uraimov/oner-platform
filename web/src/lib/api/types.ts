import type { components } from "./schema";

type Schemas = components["schemas"];

export type CourseListItem = Schemas["CourseListItem"];
export type CourseDetail = Schemas["CourseDetail"];
export type LessonDetail = Schemas["LessonDetail"];
export type CheckoutResponse = Schemas["CheckoutResponse"];
export type MyPurchase = Schemas["MyPurchase"];
export type DrmToken = Schemas["DrmTokenResponse"];
export type MaterialDownload = Schemas["MaterialDownload"];
export type CourseAdmin = Schemas["CourseAdmin"];
export type ModuleAdmin = Schemas["ModuleAdminWithMaterials"];
export type LessonAdmin = Schemas["LessonAdminWithMaterials"];
export type MaterialAdmin = Schemas["MaterialAdmin"];
export type MaterialUploadTarget = Schemas["MaterialUploadTarget"];
export type LessonVideo = Schemas["LessonVideo"];
export type VideoUploadTarget = Schemas["VideoUploadTarget"];
export type UserAdmin = Schemas["UserAdmin"];
export type UserAdminDetail = Schemas["UserAdminDetail"];
export type UserPage = Schemas["Page_UserAdmin_"];
export type PurchaseAdmin = Schemas["PurchaseAdmin"];
export type PurchasePage = Schemas["Page_PurchaseAdmin_"];
export type SweepReport = Schemas["SweepReport"];
export type EntitlementRead = Schemas["EntitlementRead"];
export type Currency = Schemas["Currency"];
export type PurchaseStatus = Schemas["PurchaseStatus"];
