import { DocsHome, docsHomeMetadata } from "@/components/docs/pages/docs-home";

export const metadata = docsHomeMetadata("en");
export const dynamic = "force-dynamic";

export default function Page() {
  return <DocsHome locale="en" />;
}
