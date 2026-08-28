import Link from "next/link";

function sourceIdValue(sourceId: string | null | undefined): string {
  return typeof sourceId === "string" ? sourceId.trim() : "";
}

function sourceTitleValue(title: string | null | undefined): string {
  return typeof title === "string" ? title.trim() : "";
}

export function SourceDetailReference({
  sourceId,
  title,
}: {
  sourceId: string | null | undefined;
  title: string | null | undefined;
}) {
  const normalizedSourceId = sourceIdValue(sourceId);
  const normalizedTitle = sourceTitleValue(title);
  const label = normalizedTitle || normalizedSourceId || "Source metadata unavailable.";

  if (!normalizedSourceId) {
    return <>{label}</>;
  }

  return (
    <Link className="provenance-source-link" href={`/sources/${encodeURIComponent(normalizedSourceId)}`}>
      {label}
    </Link>
  );
}

export function getSourceIdValue(sourceId: string | null | undefined): string {
  return sourceIdValue(sourceId);
}

export function getSourceTitleValue(title: string | null | undefined): string {
  return sourceTitleValue(title);
}
