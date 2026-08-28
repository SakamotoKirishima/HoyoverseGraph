import type { SourceDetailClaim, SourceDetailEntityRef } from "./SourceDetailView";
import {
  EMPTY_DETAIL_VALUE,
  formatEnumValue,
  formatOptionalValue,
} from "../lib/source-detail-formatting";

function entityLabel(entity: SourceDetailEntityRef): string {
  return entity.display_label?.trim() || entity.canonical_name?.trim() || entity.entity_id;
}

function formatConfidence(confidence: number | null): string {
  return confidence === null ? EMPTY_DETAIL_VALUE : String(confidence);
}

export function SourceSupportedClaims({ claims }: { claims: SourceDetailClaim[] }) {
  return (
    <section className="panel detail-section" aria-labelledby="supported-claims-heading">
      <h2 className="section-title" id="supported-claims-heading" style={{ fontSize: "1.8rem" }}>
        Supported claims
      </h2>
      {claims.length > 0 ? (
        <div className="detail-grid" style={{ marginTop: 16 }}>
          {claims.map((claim) => (
            <article className="detail-card claim-card" key={claim.claim_id}>
              <h3 className="code-line">{claim.claim_id}</h3>
              <div
                className="claim-relationship"
                aria-label={`Subject ${entityLabel(claim.subject)}; relationship ${formatEnumValue(
                  claim.predicate,
                )}; object ${entityLabel(claim.object)}`}
              >
                <div className="claim-endpoint">
                  <p className="claim-role">Subject</p>
                  <p className="claim-entity-name">{entityLabel(claim.subject)}</p>
                  <p className="code-line muted">{claim.subject.entity_id}</p>
                </div>
                <span className="claim-direction-arrow" aria-hidden="true">→</span>
                <div className="claim-predicate">
                  <p className="claim-role">Relationship</p>
                  <p className="claim-predicate-name">{formatEnumValue(claim.predicate)}</p>
                </div>
                <span className="claim-direction-arrow" aria-hidden="true">→</span>
                <div className="claim-endpoint">
                  <p className="claim-role">Object</p>
                  <p className="claim-entity-name">{entityLabel(claim.object)}</p>
                  <p className="code-line muted">{claim.object.entity_id}</p>
                </div>
              </div>
              <dl className="detail-list claim-metadata-list">
                <div>
                  <dt>Evidence status</dt>
                  <dd>{formatEnumValue(claim.evidence_status)}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{formatConfidence(claim.confidence)}</dd>
                </div>
                <div>
                  <dt>Evidence asset</dt>
                  <dd className={claim.asset_id ? "code-line" : undefined}>
                    {claim.asset_id ?? EMPTY_DETAIL_VALUE}
                  </dd>
                </div>
                <div>
                  <dt>Locator</dt>
                  <dd>{formatOptionalValue(claim.locator)}</dd>
                </div>
                <div>
                  <dt>Review status</dt>
                  <dd>{formatEnumValue(claim.review_status)}</dd>
                </div>
                <div>
                  <dt>Claim status</dt>
                  <dd>{formatEnumValue(claim.claim_status)}</dd>
                </div>
                <div className="claim-note">
                  <dt>Note</dt>
                  <dd>{formatOptionalValue(claim.note)}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted" style={{ marginTop: 16 }}>
          No claims currently reference this source.
        </p>
      )}
    </section>
  );
}
