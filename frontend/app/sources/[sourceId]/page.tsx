import { SourceDetailView } from "../../../components/SourceDetailView";

type SourceDetailPageProps = {
  params: Promise<{
    sourceId: string;
  }>;
};

export default async function SourceDetailPage({ params }: SourceDetailPageProps) {
  const { sourceId } = await params;

  return <SourceDetailView key={sourceId} sourceId={sourceId} />;
}
