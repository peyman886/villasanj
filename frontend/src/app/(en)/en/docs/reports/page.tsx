import { ReportsPage, reportsMetadata } from "@/components/docs/pages/reports";

export const metadata = reportsMetadata("en");
export const dynamic = "force-dynamic";

export default function Page() {
  return <ReportsPage locale="en" />;
}
