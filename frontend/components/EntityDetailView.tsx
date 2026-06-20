"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { buildApiUrl } from "../lib/api";

type EntityDetailEntity = {
  entity_id: string;
  canonical_name: string;
  display_label: string | null;
  entity_type: string;
  primary_scope_game: string | null;
  aliases: string[];
  short_description: string | null;
  starter_status: string | null;
  notes: string | null;
};

type EntityDetailClaim = {
  claim_id: string;
  subject_entity_id: string;
  predicate: string;
  object_entity_id: string;
  evidence_status: string | null;
  confidence: number | null;
  source_id: string | null;
  asset_id: string | null;
  locator: string | null;
  note: string | null;
  review_status: string | null;
  claim_status: string | null;
  supersedes_claim_id: string | null;
  contradicts_claim_id: string | null;
  direction: "incoming" | "outgoing";
};

type EntityDetailSource = {
  source_id: string;
  title: string;
  url: string | null;
  source_type: string;
  source_format: string;
  game: string | null;
  scope: string | null;
  reliability_tier: string | null;
  language: string | null;
  publication_date: string | null;
  notes: string | null;
};

type EntityDetailAsset = {
  asset_id: string;
  source_id: string;
  asset_type: string;
  file_path_or_url: string | null;
  locator: string | null;
  description: string | null;
  is_primary_evidence: boolean | null;
  notes: string | null;
};

type EntityDetailResponse = {
  entity: EntityDetailEntity;
  claims: EntityDetailClaim[];
  sources: EntityDetailSource[];
  assets: EntityDetailAsset[];
  graph_context: {
    seed_entity_id: string;
    graph_url: string;
    related_claim_count: number;
    related_entity_count: number;
    source_count: number;
    asset_count: number;
  };
};

type ApiErrorPayload = {
  detail?: string | string[];
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Failed to load entity details.";
}

function formatOptional(value: string | null): string {
  return value && value.trim() ? value : "Not provided";
}

function formatConfidence(value: number | null): string {
  return value === null ? "Not provided" : value.toString();
}

function isExternalUrl(value: string | null): boolean {
  return Boolean(value && /^https?:\/\//i.test(value));
}

function getGraphLink(
  graphUrl: string | null | undefined,
  entityId: string,
  depth: 1 | 2,
): string {
  const fallbackParams = new URLSearchParams({
    seed_entity_id: entityId,
    depth: depth.toString(),
  });
  const fallbackUrl = `/graph?${fallbackParams.toString()}`;

  if (!graphUrl || !graphUrl.startsWith("/graph")) {
    return fallbackUrl;
  }

  const [path, queryString = ""] = graphUrl.split("?", 2);
  const params = new URLSearchParams(queryString);
  params.set("seed_entity_id", entityId);
  params.set("depth", depth.toString());
  return `${path}?${params.toString()}`;
}

export function EntityDetailView({ entityId }: { entityId: string }) {
  const [data, setData] = useState<EntityDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!entityId) {
      setLoading(false);
      setError("Entity ID is missing from the route.");
      return;
    }

    const controller = new AbortController();

    async function loadEntityDetail() {
      setLoading(true);
      setError(null);
      setNotFound(false);

      try {
        const response = await fetch(buildApiUrl(`/entities/${entityId}/detail`), {
          method: "GET",
          headers: {
            Accept: "application/json",
          },
          signal: controller.signal,
          cache: "no-store",
        });

        if (response.status === 404) {
          setData(null);
          setNotFound(true);
          return;
        }

        if (!response.ok) {
          let message = `Entity detail request failed with status ${response.status}.`;
          try {
            const payload = (await response.json()) as ApiErrorPayload;
            if (Array.isArray(payload.detail)) {
              message = payload.detail.join(" ");
            } else if (typeof payload.detail === "string") {
              message = payload.detail;
            }
          } catch {
            // Keep fallback message if payload is not JSON.
          }
          throw new Error(message);
        }

        const payload = (await response.json()) as EntityDetailResponse;
        setData(payload);
      } catch (fetchError) {
        if ((fetchError as Error).name === "AbortError") {
          return;
        }
        setData(null);
        setError(getErrorMessage(fetchError));
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadEntityDetail();

    return () => controller.abort();
  }, [entityId]);

  const entity = data?.entity;
  const heading = entity?.display_label || entity?.canonical_name || entityId;
  const showCanonicalName =
    entity?.display_label &&
    entity.canonical_name &&
    entity.display_label.trim() !== entity.canonical_name.trim();
  const graphContext = data?.graph_context;
  const graphLinkDepth1 = getGraphLink(graphContext?.graph_url, entityId, 1);
  const graphLinkDepth2 = getGraphLink(graphContext?.graph_url, entityId, 2);
  const sourcesById = new Map(data?.sources.map((source) => [source.source_id, source]) ?? []);
  const assetsById = new Map(data?.assets.map((asset) => [asset.asset_id, asset]) ?? []);

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Entity Detail</p>
        <h1 className="page-title">{heading}</h1>
        <p className="lead">
          Canonical entity metadata from the consolidated detail endpoint.
        </p>
        <div className="hero-links">
          <Link className="hero-link" href="/search">
            Back to search
          </Link>
        </div>
      </section>

      {loading ? (
        <section className="panel">
          <p className="message">Loading entity details...</p>
        </section>
      ) : null}

      {notFound ? (
        <section className="panel">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Entity not found
          </h2>
          <p className="muted">
            No entity detail record was found for <span className="code-line">{entityId}</span>.
          </p>
        </section>
      ) : null}

      {error ? (
        <section className="panel">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Could not load entity details
          </h2>
          <p className="message error">{error}</p>
        </section>
      ) : null}

      {!loading && !error && !notFound && entity ? (
        <section className="panel detail-section">
          <div className="detail-grid">
            <article className="detail-card">
              <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
                Canonical metadata
              </h2>
              <dl className="detail-list" style={{ marginTop: 16 }}>
                <div>
                  <dt>Display label</dt>
                  <dd>{formatOptional(entity.display_label)}</dd>
                </div>
                {showCanonicalName ? (
                  <div>
                    <dt>Canonical name</dt>
                    <dd>{entity.canonical_name}</dd>
                  </div>
                ) : null}
                <div>
                  <dt>Entity ID</dt>
                  <dd className="code-line">{entity.entity_id}</dd>
                </div>
                <div>
                  <dt>Entity type</dt>
                  <dd>{entity.entity_type}</dd>
                </div>
                <div>
                  <dt>Primary scope game</dt>
                  <dd>{formatOptional(entity.primary_scope_game)}</dd>
                </div>
                <div>
                  <dt>Short description</dt>
                  <dd>{formatOptional(entity.short_description)}</dd>
                </div>
                <div>
                  <dt>Starter status</dt>
                  <dd>{formatOptional(entity.starter_status)}</dd>
                </div>
                <div>
                  <dt>Notes</dt>
                  <dd>{formatOptional(entity.notes)}</dd>
                </div>
              </dl>
            </article>

            <article className="detail-card">
              <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
                Aliases ({entity.aliases.length})
              </h2>
              {entity.aliases.length > 0 ? (
                <div className="chip-row" style={{ marginTop: 16 }}>
                  {entity.aliases.map((alias) => (
                    <span className="chip" key={alias}>
                      {alias}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="muted" style={{ marginTop: 16 }}>
                  No aliases listed.
                </p>
              )}
            </article>
          </div>
        </section>
      ) : null}

      {!loading && !error && !notFound && graphContext ? (
        <section className="panel detail-section">
          <div className="detail-grid">
            <article className="detail-card">
              <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
                Graph Context
              </h2>
              <p className="muted" style={{ marginTop: 12 }}>
                Open this entity as the seed node in the graph view for a connected
                claims-and-relationships perspective.
              </p>

              <div className="hero-links" style={{ marginTop: 16 }}>
                <Link className="hero-link" href={graphLinkDepth1}>
                  View 1-hop graph
                </Link>
                <Link className="hero-link hero-link-secondary" href={graphLinkDepth2}>
                  View 2-hop graph
                </Link>
              </div>
            </article>

            <article className="detail-card">
              <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
                Graph Summary
              </h2>
              <dl className="detail-list" style={{ marginTop: 16 }}>
                <div>
                  <dt>Claims</dt>
                  <dd>{graphContext.related_claim_count}</dd>
                </div>
                <div>
                  <dt>Related entities</dt>
                  <dd>{graphContext.related_entity_count}</dd>
                </div>
                <div>
                  <dt>Sources</dt>
                  <dd>{graphContext.source_count}</dd>
                </div>
                <div>
                  <dt>Assets</dt>
                  <dd>{graphContext.asset_count}</dd>
                </div>
              </dl>
            </article>
          </div>
        </section>
      ) : null}

      {!loading && !error && !notFound && data ? (
        <section className="panel detail-section">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Related Claims ({data.claims.length})
          </h2>

          {data.claims.length > 0 ? (
            <div className="detail-grid" style={{ marginTop: 16 }}>
              {data.claims.map((claim) => (
                <article className="detail-card" key={claim.claim_id}>
                  <h3>{claim.claim_id}</h3>
                  <p className="muted" style={{ marginTop: 8 }}>
                    <strong>{claim.direction === "outgoing" ? "Outgoing" : "Incoming"}:</strong>{" "}
                    <span className="code-line">{claim.subject_entity_id}</span> → {claim.predicate} →{" "}
                    <span className="code-line">{claim.object_entity_id}</span>
                  </p>

                  <dl className="detail-list" style={{ marginTop: 16 }}>
                    <div>
                      <dt>Predicate</dt>
                      <dd>{claim.predicate}</dd>
                    </div>
                    <div>
                      <dt>Subject entity ID</dt>
                      <dd className="code-line">{claim.subject_entity_id}</dd>
                    </div>
                    <div>
                      <dt>Object entity ID</dt>
                      <dd className="code-line">{claim.object_entity_id}</dd>
                    </div>
                    <div>
                      <dt>Evidence status</dt>
                      <dd>{formatOptional(claim.evidence_status)}</dd>
                    </div>
                    <div>
                      <dt>Confidence</dt>
                      <dd>{formatConfidence(claim.confidence)}</dd>
                    </div>
                    <div>
                      <dt>Claim status</dt>
                      <dd>{formatOptional(claim.claim_status)}</dd>
                    </div>
                    {claim.note ? (
                      <div>
                        <dt>Note</dt>
                        <dd>{claim.note}</dd>
                      </div>
                    ) : null}
                  </dl>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ marginTop: 16 }}>
              No related claims found.
            </p>
          )}
        </section>
      ) : null}

      {!loading && !error && !notFound && data ? (
        <section className="panel detail-section">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Related Sources ({data.sources.length})
          </h2>

          {data.sources.length > 0 ? (
            <div className="detail-grid" style={{ marginTop: 16 }}>
              {data.sources.map((source) => (
                <article className="detail-card" key={source.source_id}>
                  <h3>{source.title}</h3>
                  <p className="muted code-line" style={{ marginTop: 8 }}>
                    {source.source_id}
                  </p>

                  <dl className="detail-list" style={{ marginTop: 16 }}>
                    <div>
                      <dt>Source type</dt>
                      <dd>{source.source_type}</dd>
                    </div>
                    <div>
                      <dt>Source format</dt>
                      <dd>{source.source_format}</dd>
                    </div>
                    <div>
                      <dt>Game</dt>
                      <dd>{formatOptional(source.game)}</dd>
                    </div>
                    <div>
                      <dt>Scope</dt>
                      <dd>{formatOptional(source.scope)}</dd>
                    </div>
                    <div>
                      <dt>Reliability tier</dt>
                      <dd>{formatOptional(source.reliability_tier)}</dd>
                    </div>
                    <div>
                      <dt>URL</dt>
                      <dd>
                        {source.url ? (
                          <a
                            className="external-link"
                            href={source.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {source.url}
                          </a>
                        ) : (
                          "No public URL"
                        )}
                      </dd>
                    </div>
                    {source.notes ? (
                      <div>
                        <dt>Notes</dt>
                        <dd>{source.notes}</dd>
                      </div>
                    ) : null}
                  </dl>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ marginTop: 16 }}>
              No related sources found.
            </p>
          )}
        </section>
      ) : null}

      {!loading && !error && !notFound && data ? (
        <section className="panel detail-section">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Linked Evidence Assets ({data.assets.length})
          </h2>

          {data.assets.length > 0 ? (
            <div className="detail-grid" style={{ marginTop: 16 }}>
              {data.assets.map((asset) => (
                <article className="detail-card" key={asset.asset_id}>
                  <h3>{asset.asset_id}</h3>
                  <dl className="detail-list" style={{ marginTop: 16 }}>
                    <div>
                      <dt>Source ID</dt>
                      <dd className="code-line">{asset.source_id}</dd>
                    </div>
                    <div>
                      <dt>Asset type</dt>
                      <dd>{asset.asset_type}</dd>
                    </div>
                    <div>
                      <dt>Locator</dt>
                      <dd>{formatOptional(asset.locator)}</dd>
                    </div>
                    <div>
                      <dt>Description</dt>
                      <dd>{formatOptional(asset.description)}</dd>
                    </div>
                    <div>
                      <dt>Primary evidence</dt>
                      <dd>{asset.is_primary_evidence ? "Yes" : "No"}</dd>
                    </div>
                    <div>
                      <dt>File or URL</dt>
                      <dd>
                        {asset.file_path_or_url ? (
                          isExternalUrl(asset.file_path_or_url) ? (
                            <a
                              className="external-link"
                              href={asset.file_path_or_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {asset.file_path_or_url}
                            </a>
                          ) : (
                            <span className="code-line">{asset.file_path_or_url}</span>
                          )
                        ) : (
                          "Not provided"
                        )}
                      </dd>
                    </div>
                    {asset.notes ? (
                      <div>
                        <dt>Notes</dt>
                        <dd>{asset.notes}</dd>
                      </div>
                    ) : null}
                  </dl>
                </article>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ marginTop: 16 }}>
              No linked evidence assets found.
            </p>
          )}
        </section>
      ) : null}

      {!loading && !error && !notFound && data ? (
        <section className="panel detail-section">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Evidence & Provenance
          </h2>

          {data.claims.length > 0 ? (
            <div className="detail-grid" style={{ marginTop: 16 }}>
              {data.claims.map((claim) => {
                const linkedSource = claim.source_id ? sourcesById.get(claim.source_id) : null;
                const linkedAsset = claim.asset_id ? assetsById.get(claim.asset_id) : null;

                return (
                  <article className="detail-card provenance-card" key={`${claim.claim_id}-provenance`}>
                    <h3>{claim.claim_id}</h3>
                    <p className="muted" style={{ marginTop: 8 }}>
                      <strong>{claim.direction === "outgoing" ? "Outgoing" : "Incoming"}:</strong>{" "}
                      <span className="code-line">{claim.subject_entity_id}</span> → {claim.predicate} →{" "}
                      <span className="code-line">{claim.object_entity_id}</span>
                    </p>

                    <dl className="detail-list" style={{ marginTop: 16 }}>
                      <div>
                        <dt>Predicate</dt>
                        <dd>{claim.predicate}</dd>
                      </div>
                      <div>
                        <dt>Evidence status</dt>
                        <dd>{formatOptional(claim.evidence_status)}</dd>
                      </div>
                      <div>
                        <dt>Confidence</dt>
                        <dd>{formatConfidence(claim.confidence)}</dd>
                      </div>
                      <div>
                        <dt>Source ID</dt>
                        <dd>{claim.source_id ? <span className="code-line">{claim.source_id}</span> : "No source linked."}</dd>
                      </div>
                      <div>
                        <dt>Asset ID</dt>
                        <dd>{claim.asset_id ? <span className="code-line">{claim.asset_id}</span> : "No evidence asset linked."}</dd>
                      </div>
                      {claim.locator ? (
                        <div>
                          <dt>Locator</dt>
                          <dd>{claim.locator}</dd>
                        </div>
                      ) : null}
                      {claim.note ? (
                        <div>
                          <dt>Note</dt>
                          <dd>{claim.note}</dd>
                        </div>
                      ) : null}
                    </dl>

                    <div className="provenance-block">
                      <h4>Source record</h4>
                      {!claim.source_id ? (
                        <p className="muted">No source linked.</p>
                      ) : linkedSource ? (
                        <dl className="detail-list">
                          <div>
                            <dt>Title</dt>
                            <dd>{linkedSource.title}</dd>
                          </div>
                          <div>
                            <dt>Type</dt>
                            <dd>{linkedSource.source_type}</dd>
                          </div>
                          <div>
                            <dt>Format</dt>
                            <dd>{linkedSource.source_format}</dd>
                          </div>
                          <div>
                            <dt>Reliability</dt>
                            <dd>{formatOptional(linkedSource.reliability_tier)}</dd>
                          </div>
                          <div>
                            <dt>URL</dt>
                            <dd>
                              {linkedSource.url ? (
                                <a
                                  className="external-link"
                                  href={linkedSource.url}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  {linkedSource.url}
                                </a>
                              ) : (
                                "No public URL"
                              )}
                            </dd>
                          </div>
                        </dl>
                      ) : (
                        <p className="muted">Source metadata unavailable.</p>
                      )}
                    </div>

                    <div className="provenance-block">
                      <h4>Evidence asset</h4>
                      {!claim.asset_id ? (
                        <p className="muted">No evidence asset linked.</p>
                      ) : linkedAsset ? (
                        <dl className="detail-list">
                          <div>
                            <dt>Asset type</dt>
                            <dd>{linkedAsset.asset_type}</dd>
                          </div>
                          <div>
                            <dt>Locator</dt>
                            <dd>{formatOptional(linkedAsset.locator)}</dd>
                          </div>
                          <div>
                            <dt>Description</dt>
                            <dd>{formatOptional(linkedAsset.description)}</dd>
                          </div>
                          <div>
                            <dt>Primary evidence</dt>
                            <dd>{linkedAsset.is_primary_evidence ? "Yes" : "No"}</dd>
                          </div>
                          <div>
                            <dt>File or URL</dt>
                            <dd>
                              {linkedAsset.file_path_or_url ? (
                                isExternalUrl(linkedAsset.file_path_or_url) ? (
                                  <a
                                    className="external-link"
                                    href={linkedAsset.file_path_or_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    {linkedAsset.file_path_or_url}
                                  </a>
                                ) : (
                                  <span className="code-line">{linkedAsset.file_path_or_url}</span>
                                )
                              ) : (
                                "Not provided"
                              )}
                            </dd>
                          </div>
                        </dl>
                      ) : (
                        <p className="muted">Asset metadata unavailable.</p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="muted" style={{ marginTop: 16 }}>
              No provenance records available.
            </p>
          )}
        </section>
      ) : null}
    </main>
  );
}
