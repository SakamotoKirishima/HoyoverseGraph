import type { SourceDetailSource } from "./SourceDetailView";
import { EMPTY_DETAIL_VALUE, formatEnumValue, formatOptionalValue } from "../lib/source-detail-formatting";

function formatPublicationDate(value: string | null): string {
  if (!value?.trim()) {
    return EMPTY_DETAIL_VALUE;
  }

  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return value;
  }

  const [, year, month, day] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day)));
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function SourceMetadataSection({ source }: { source: SourceDetailSource }) {
  const sourceUrl = source.url?.trim() || null;

  return (
    <section className="panel detail-section" aria-labelledby="source-metadata-heading">
      <h2 className="section-title" id="source-metadata-heading" style={{ fontSize: "1.8rem" }}>
        Source metadata
      </h2>
      <dl className="detail-list source-metadata-list" style={{ marginTop: 16 }}>
        <div>
          <dt>Source ID</dt>
          <dd className="code-line">{source.source_id}</dd>
        </div>
        <div>
          <dt>Source type</dt>
          <dd>{formatEnumValue(source.source_type)}</dd>
        </div>
        <div>
          <dt>Source format</dt>
          <dd>{formatEnumValue(source.source_format)}</dd>
        </div>
        <div>
          <dt>Game</dt>
          <dd>{formatOptionalValue(source.game)}</dd>
        </div>
        <div>
          <dt>Scope</dt>
          <dd>{formatEnumValue(source.scope)}</dd>
        </div>
        <div>
          <dt>Reliability tier</dt>
          <dd>{formatEnumValue(source.reliability_tier)}</dd>
        </div>
        <div>
          <dt>Language</dt>
          <dd>{formatOptionalValue(source.language)}</dd>
        </div>
        <div>
          <dt>Publication date</dt>
          <dd>{formatPublicationDate(source.publication_date)}</dd>
        </div>
        {sourceUrl ? (
          <div>
            <dt>Source URL</dt>
            <dd>
              <a
                className="external-link"
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                View original source
              </a>
            </dd>
          </div>
        ) : null}
        <div>
          <dt>Notes</dt>
          <dd>{formatOptionalValue(source.notes)}</dd>
        </div>
      </dl>
    </section>
  );
}
