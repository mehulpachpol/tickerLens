import { ChatApp } from "@/components/ChatApp";
import { requireSignedIn } from "@/lib/serverAuth";

export default async function Page() {
  await requireSignedIn("/");
  return <ChatApp />;
}
