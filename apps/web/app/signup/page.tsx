import { SignupClient } from "@/components/auth/SignupClient";

export default async function SignupPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = (await searchParams) ?? {};
  const nextParam = sp.next;
  const nextUrl = Array.isArray(nextParam) ? nextParam[0] : nextParam;
  return <SignupClient nextUrl={nextUrl ?? "/"} />;
}
