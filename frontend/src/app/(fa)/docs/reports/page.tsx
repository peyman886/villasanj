import { ReportsPage, reportsMetadata } from "@/components/docs/pages/reports";

export const metadata = reportsMetadata("fa");
export const dynamic = "force-dynamic";

export default function Page() {
  return <ReportsPage locale="fa" />;
}
