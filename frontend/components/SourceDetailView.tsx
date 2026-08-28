"use client";

import { useEffect, useState } from "react";

import { buildApiUrl } from "../lib/api";
import { SourceEvidenceAssets } from "./SourceEvidenceAssets";
import { SourceMetadataSection } from "./SourceMetadataSection";
import { SourceSupportedClaims } from "./SourceSupportedClaims";

export type SourceDetailSource = {
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

export type SourceDetailAsset = {
  asset_id: string;
  source_id: string;
  asset_type: string;
  file_path_or_url: string | null;
  locator: string | null;
  description: string | null;
  is_primary_evidence: boolean | null;
  notes: string | null;
};

export type SourceDetailEntityRef = {
  entity_id: string;
  canonical_name: string;
  display_label: string | null;
  entity_type: string;
  primary_scope_game: string | null;
};

export type SourceDetailClaim = {
  claim_id: string;
  subject: SourceDetailEntityRef;
  predicate: string;
  object: SourceDetailEntityRef;
  evidence_status: string | null;
  confidence: number | null;
  asset_id: string | null;
  locator: string | null;
  note: string | null;
  review_status: string | null;
  claim_status: string | null;
};

export type SourceDetailSummary = {
  claim_count: number;
  asset_count: number;
  primary_evidence_asset_count: number;
  related_entity_count: number;
};

export type SourceDetailResponse = {
  source: SourceDetailSource;
  assets: SourceDetailAsset[];
  claims: SourceDetailClaim[];
  summary: SourceDetailSummary;
};

type ApiErrorPayload = {
  detail?: string | string[];
};

export function SourceDetailView({ sourceId }: { sourceId: string }) {
  const [data, setData] = useState<SourceDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [invalidSourceId, setInvalidSourceId] = useState(false);

  useEffect(() => {
    if (!sourceId) {
      setData(null);
      setLoading(false);
      setError(false);
      setNotFound(false);
      setInvalidSourceId(true);
      return;
    }

    const controller = new AbortController();

    async function loadSourceDetail() {
      setData(null);
      setLoading(true);
      setError(false);
      setNotFound(false);
      setInvalidSourceId(false);

      try {
        const response = await fetch(
          buildApiUrl(`/sources/${encodeURIComponent(sourceId)}/detail`),
          {
            method: "GET",
            headers: { Accept: "application/json" },
            signal: controller.signal,
            cache: "no-store",
          },
        );

        if (response.status === 404) {
          setNotFound(true);
          return;
        }

        if (response.status === 422) {
          setInvalidSourceId(true);
          return;
        }

        if (!response.ok) {
          try {
            await response.json() as ApiErrorPayload;
          } catch {
            // The user-facing error stays generic whether or not the body is JSON.
          }
          throw new Error("Source detail request failed.");
        }

        setData((await response.json()) as SourceDetailResponse);
      } catch (fetchError) {
        if ((fetchError as Error).name !== "AbortError") {
          setError(true);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadSourceDetail();

    return () => controller.abort();
  }, [sourceId]);

  const source = data?.source;
  const heading = source?.title?.trim() || sourceId;

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">Source Detail</p>
        <h1 className="page-title">{heading}</h1>
        <p className="lead">
          Source-centric evidence, supporting claims, and canonical source metadata.
        </p>
        <p className="code-line">{source?.source_id ?? sourceId}</p>
      </header>

      {loading ? (
        <section className="panel" aria-live="polite">
          <p className="message">Loading source details...</p>
        </section>
      ) : null}

      {notFound ? (
        <section className="panel">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Source not found
          </h2>
          <p className="muted">
            No source exists with ID <span className="code-line">{sourceId}</span>.
          </p>
        </section>
      ) : null}

      {invalidSourceId ? (
        <section className="panel">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Invalid source ID
          </h2>
          <p className="muted">The source ID in this URL is not valid.</p>
        </section>
      ) : null}

      {error ? (
        <section className="panel">
          <h2 className="section-title" style={{ fontSize: "1.8rem" }}>
            Unable to load this source
          </h2>
          <p className="message error">Please try again.</p>
        </section>
      ) : null}

      {!loading && !error && !notFound && !invalidSourceId && data && source ? (
        <>
          <section className="panel detail-section" aria-labelledby="source-summary-heading">
            <h2 className="section-title" id="source-summary-heading" style={{ fontSize: "1.8rem" }}>
              Summary
            </h2>
            <div className="detail-grid" style={{ marginTop: 16 }}>
              <article className="detail-card">
                <h3>Claims</h3>
                <p className="muted">{data.summary.claim_count}</p>
              </article>
              <article className="detail-card">
                <h3>Assets</h3>
                <p className="muted">{data.summary.asset_count}</p>
              </article>
              <article className="detail-card">
                <h3>Primary evidence assets</h3>
                <p className="muted">{data.summary.primary_evidence_asset_count}</p>
              </article>
              <article className="detail-card">
                <h3>Related entities</h3>
                <p className="muted">{data.summary.related_entity_count}</p>
              </article>
            </div>
          </section>

          <SourceMetadataSection source={source} />

          <SourceEvidenceAssets assets={data.assets} />

          <SourceSupportedClaims claims={data.claims} />
        </>
      ) : null}
    </main>
  );
}
