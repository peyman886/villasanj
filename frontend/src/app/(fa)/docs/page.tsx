import { DocsHome, docsHomeMetadata } from "@/components/docs/pages/docs-home";

export const metadata = docsHomeMetadata("fa");
export const dynamic = "force-dynamic";

export default function Page() {
  return <DocsHome locale="fa" />;
}
