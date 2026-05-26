import { LoginClient } from "@/components/auth/LoginClient";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = (await searchParams) ?? {};
  const nextParam = sp.next;
  const nextUrl = Array.isArray(nextParam) ? nextParam[0] : nextParam;
  return <LoginClient nextUrl={nextUrl ?? "/"} />;
}
