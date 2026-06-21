import { EntityDetailView } from "../../../components/EntityDetailView";

type EntityDetailPageProps = {
  params: Promise<{
    entityId: string;
  }>;
};

export default async function EntityDetailPage({ params }: EntityDetailPageProps) {
  const { entityId } = await params;

  return <EntityDetailView entityId={entityId} />;
}
