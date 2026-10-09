import { DecisionsPage, decisionsMetadata } from "@/components/docs/pages/decisions";

export const metadata = decisionsMetadata("en");
export const dynamic = "force-dynamic";

export default function Page() {
  return <DecisionsPage locale="en" />;
}
