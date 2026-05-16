import { redirect } from "next/navigation";

/** Coverage lives on the project home (#coverage). */
export default function ProjectCoverageRedirect({
  params,
}: {
  params: { id: string };
}) {
  redirect(`/projects/${params.id}#coverage`);
}
