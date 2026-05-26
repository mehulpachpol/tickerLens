import { TimelineApp } from "@/components/TimelineApp";
import { requireSignedIn } from "@/lib/serverAuth";

export default async function TimelinePage() {
  await requireSignedIn("/timeline");
  return <TimelineApp />;
}
