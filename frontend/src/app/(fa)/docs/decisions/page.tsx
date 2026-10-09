import { DecisionsPage, decisionsMetadata } from "@/components/docs/pages/decisions";

export const metadata = decisionsMetadata("fa");
export const dynamic = "force-dynamic";

export default function Page() {
  return <DecisionsPage locale="fa" />;
}
