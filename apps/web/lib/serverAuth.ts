import { apiBaseUrl } from "@/lib/apiProxy";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function cookieHeaderFromStore(): Promise<string> {
  const store = await cookies();
  const all = store.getAll();
  return all.map((c) => `${c.name}=${c.value}`).join("; ");
}

export async function requireSignedIn(nextUrl: string): Promise<void> {
  const baseUrl = apiBaseUrl();
  const cookie = await cookieHeaderFromStore();

  let res: Response;
  try {
    res = await fetch(`${baseUrl}/auth/me`, {
      method: "GET",
      headers: { Accept: "application/json", ...(cookie ? { cookie } : {}) },
      cache: "no-store",
    });
  } catch {
    redirect("/auth-disabled");
  }

  if (res.status === 200) return;
  if (res.status === 401) redirect(`/login?next=${encodeURIComponent(nextUrl)}`);
  if (res.status === 400) redirect("/auth-disabled");
  redirect(`/login?next=${encodeURIComponent(nextUrl)}`);
}
