import { notFound } from "next/navigation";
import { UserDetailAdmin } from "@/components/admin/user-detail";

export default async function AdminUserPage(props: PageProps<"/admin/users/[id]">) {
  const { id } = await props.params;
  const userId = Number(id);
  if (!Number.isInteger(userId) || userId <= 0) notFound();
  return <UserDetailAdmin userId={userId} />;
}
