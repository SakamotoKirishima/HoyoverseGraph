import { EntityDetailView } from "../../../components/EntityDetailView";

type EntityDetailPageProps = {
  params: {
    entityId: string;
  };
};

export default function EntityDetailPage({ params }: EntityDetailPageProps) {
  return <EntityDetailView entityId={params.entityId} />;
}
