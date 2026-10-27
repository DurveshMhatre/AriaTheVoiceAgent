import { redirect } from "next/navigation";
import CallExperience from "@/components/CallExperience";
import { createClient } from "@/lib/auth/server";

export const dynamic = "force-dynamic";
export default async function CallPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user || !user.email_confirmed_at) redirect("/login");
  return <CallExperience email={user.email ?? "Evaluator"} />;
}
