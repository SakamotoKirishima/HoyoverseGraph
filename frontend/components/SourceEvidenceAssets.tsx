import type { SourceDetailAsset } from "./SourceDetailView";
import { ExternalLink } from "./ExternalLink";
import {
  EMPTY_DETAIL_VALUE,
  formatEnumValue,
  formatOptionalValue,
} from "../lib/source-detail-formatting";
import { isHttpUrl } from "../lib/external-links";

function evidenceStatus(asset: SourceDetailAsset): string {
  if (asset.is_primary_evidence === true) {
    return "Primary evidence";
  }
  if (asset.is_primary_evidence === false) {
    return "Supporting evidence";
  }
  return "Evidence status not specified";
}

export function SourceEvidenceAssets({ assets }: { assets: SourceDetailAsset[] }) {
  return (
    <section className="panel detail-section" aria-labelledby="evidence-assets-heading">
      <h2 className="section-title" id="evidence-assets-heading" style={{ fontSize: "1.8rem" }}>
        Evidence assets
      </h2>
      {assets.length > 0 ? (
        <div className="detail-grid" style={{ marginTop: 16 }}>
          {assets.map((asset) => {
            const evidenceReference = asset.file_path_or_url?.trim() ? asset.file_path_or_url : null;
            const isExternalEvidence = evidenceReference ? isHttpUrl(evidenceReference) : false;

            return (
              <article className="detail-card evidence-card" key={asset.asset_id}>
                <div>
                  <h3 className="code-line">{asset.asset_id}</h3>
                  <p className="muted">{formatEnumValue(asset.asset_type)}</p>
                </div>
                <p className="chip evidence-status">{evidenceStatus(asset)}</p>
                <dl className="detail-list">
                  <div>
                    <dt>Locator</dt>
                    <dd>{formatOptionalValue(asset.locator)}</dd>
                  </div>
                  <div>
                    <dt>Description</dt>
                    <dd>{formatOptionalValue(asset.description)}</dd>
                  </div>
                  <div>
                    <dt>{isExternalEvidence ? "Evidence" : "Evidence reference"}</dt>
                    <dd>
                      {isExternalEvidence && evidenceReference ? (
                        <ExternalLink href={evidenceReference}>
                          View evidence
                        </ExternalLink>
                      ) : evidenceReference ? (
                        <span className="code-line">{evidenceReference}</span>
                      ) : (
                        EMPTY_DETAIL_VALUE
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>Notes</dt>
                    <dd>{formatOptionalValue(asset.notes)}</dd>
                  </div>
                </dl>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="muted" style={{ marginTop: 16 }}>
          No evidence assets are recorded for this source.
        </p>
      )}
    </section>
  );
}
