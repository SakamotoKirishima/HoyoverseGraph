"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { buildApiUrl } from "../lib/api";

type GraphElementDefinition = {
  data: Record<string, string | number | null>;
};

type GraphCore = {
  destroy(): void;
  on(
    eventName: string,
    selectorOrHandler: string | ((event: unknown) => void),
    handler?: (event: unknown) => void,
  ): void;
  elements(): {
    unselect(): void;
  };
};

type GraphNode = {
  id: string;
  entity_id: string;
  label: string;
  canonical_name: string;
  entity_type: string;
  primary_scope_game: string | null;
  short_description: string | null;
};

type GraphEdge = {
  id: string;
  claim_id: string;
  source: string;
  target: string;
  predicate: string;
  confidence: number | null;
  evidence_status: string | null;
  source_id: string | null;
  asset_id: string | null;
  claim_status: string | null;
};

type GraphResponse = {
  seed_entity_id: string;
  depth: 1 | 2;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

type EntityDetails = {
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

type ClaimEntitySummary = {
  entity_id: string;
  canonical_name: string;
  display_label?: string | null;
};

type ClaimSourceSummary = {
  source_id: string;
  title?: string | null;
};

type ClaimAssetSummary = {
  asset_id: string;
  description?: string | null;
};

type ClaimDetails = {
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
  subject_entity: ClaimEntitySummary | null;
  object_entity: ClaimEntitySummary | null;
  source: ClaimSourceSummary | null;
  asset: ClaimAssetSummary | null;
};

type SelectedElement =
  | { kind: "node"; data: GraphNode }
  | { kind: "edge"; data: GraphEdge }
  | null;

type FormState = {
  seedEntityId: string;
  depth: "1" | "2";
  predicate: string;
  confidenceMin: string;
  evidenceStatus: string;
};

type SearchParamReader = {
  get(name: string): string | null;
};

function createFormStateFromSearchParams(searchParams: SearchParamReader): FormState {
  const depthValue = searchParams.get("depth");
  return {
    seedEntityId: searchParams.get("seed_entity_id") ?? "",
    depth: depthValue === "2" ? "2" : "1",
    predicate: searchParams.get("predicate") ?? "",
    confidenceMin: searchParams.get("confidence_min") ?? "",
    evidenceStatus: searchParams.get("evidence_status") ?? "",
  };
}

function toApiSearchParams(formState: FormState): URLSearchParams {
  const params = new URLSearchParams();
  params.set("seed_entity_id", formState.seedEntityId.trim());
  params.set("depth", formState.depth);
  params.set("limit", "100");

  const predicate = formState.predicate.trim();
  const confidenceMin = formState.confidenceMin.trim();
  const evidenceStatus = formState.evidenceStatus.trim();

  if (predicate) {
    params.set("predicate", predicate);
  }
  if (confidenceMin) {
    params.set("confidence_min", confidenceMin);
  }
  if (evidenceStatus) {
    params.set("evidence_status", evidenceStatus);
  }

  return params;
}

function toCytoscapeElements(graph: GraphResponse): GraphElementDefinition[] {
  const nodeElements: GraphElementDefinition[] = graph.nodes.map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      entity_id: node.entity_id,
      canonical_name: node.canonical_name,
      entity_type: node.entity_type,
      primary_scope_game: node.primary_scope_game,
      short_description: node.short_description,
    },
  }));

  const edgeElements: GraphElementDefinition[] = graph.edges.map((edge) => ({
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.predicate,
      claim_id: edge.claim_id,
      predicate: edge.predicate,
      confidence: edge.confidence,
      evidence_status: edge.evidence_status,
      source_id: edge.source_id,
      asset_id: edge.asset_id,
      claim_status: edge.claim_status,
    },
  }));

  return [...nodeElements, ...edgeElements];
}

export function GraphViewer() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cytoscapeRef = useRef<GraphCore | null>(null);

  const derivedFormState = useMemo(
    () => createFormStateFromSearchParams(searchParams),
    [searchParams],
  );

  const [formState, setFormState] = useState<FormState>(derivedFormState);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [selectedElement, setSelectedElement] = useState<SelectedElement>(null);
  const [selectedEntityDetails, setSelectedEntityDetails] = useState<EntityDetails | null>(null);
  const [entityDetailsLoading, setEntityDetailsLoading] = useState(false);
  const [entityDetailsError, setEntityDetailsError] = useState<string | null>(null);
  const [selectedClaimDetails, setSelectedClaimDetails] = useState<ClaimDetails | null>(null);
  const [claimDetailsLoading, setClaimDetailsLoading] = useState(false);
  const [claimDetailsError, setClaimDetailsError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    setFormState(derivedFormState);
  }, [derivedFormState]);

  useEffect(() => {
    const seedEntityId = derivedFormState.seedEntityId.trim();
    if (!seedEntityId) {
      setGraphData(null);
      setSelectedElement(null);
      setSelectedEntityDetails(null);
      setSelectedClaimDetails(null);
      return;
    }

    const controller = new AbortController();

    async function loadGraph() {
      setLoading(true);
      setError(null);
      setValidationMessage(null);

      try {
        const response = await fetch(
          buildApiUrl("/graph", toApiSearchParams(derivedFormState)),
          {
            method: "GET",
            signal: controller.signal,
            headers: {
              Accept: "application/json",
            },
          },
        );

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as
            | { detail?: string | string[] }
            | null;
          const detail = Array.isArray(payload?.detail)
            ? payload.detail.join(" ")
            : payload?.detail;
          throw new Error(detail || `Graph request failed with status ${response.status}.`);
        }

        const payload = (await response.json()) as GraphResponse;
        setGraphData(payload);
        setSelectedElement(null);
        setSelectedEntityDetails(null);
        setSelectedClaimDetails(null);
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }
        const message =
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load graph data.";
        setGraphData(null);
        setSelectedElement(null);
        setSelectedEntityDetails(null);
        setSelectedClaimDetails(null);
        setError(message);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadGraph();

    return () => {
      controller.abort();
    };
  }, [derivedFormState]);

  useEffect(() => {
    if (selectedElement?.kind !== "node") {
      setSelectedEntityDetails(null);
      setEntityDetailsLoading(false);
      setEntityDetailsError(null);
      return;
    }

    const selectedNode = selectedElement.data;
    const controller = new AbortController();

    async function loadEntityDetails() {
      setSelectedEntityDetails(null);
      setEntityDetailsLoading(true);
      setEntityDetailsError(null);

      try {
        const response = await fetch(
          buildApiUrl(`/entities/${selectedNode.entity_id}`),
          {
            method: "GET",
            signal: controller.signal,
            headers: {
              Accept: "application/json",
            },
          },
        );

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as
            | { detail?: string | string[] }
            | null;
          const detail = Array.isArray(payload?.detail)
            ? payload.detail.join(" ")
            : payload?.detail;
          throw new Error(detail || `Entity request failed with status ${response.status}.`);
        }

        const payload = (await response.json()) as EntityDetails;
        if (!controller.signal.aborted) {
          setSelectedEntityDetails(payload);
        }
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }
        const message =
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load full entity details.";
        setSelectedEntityDetails(null);
        setEntityDetailsError(message);
      } finally {
        if (!controller.signal.aborted) {
          setEntityDetailsLoading(false);
        }
      }
    }

    void loadEntityDetails();

    return () => {
      controller.abort();
    };
  }, [selectedElement]);

  useEffect(() => {
    if (selectedElement?.kind !== "edge") {
      setSelectedClaimDetails(null);
      setClaimDetailsLoading(false);
      setClaimDetailsError(null);
      return;
    }

    const selectedEdge = selectedElement.data;
    const controller = new AbortController();

    async function loadClaimDetails() {
      setSelectedClaimDetails(null);
      setClaimDetailsLoading(true);
      setClaimDetailsError(null);

      try {
        const response = await fetch(
          buildApiUrl(`/claims/${selectedEdge.claim_id}`),
          {
            method: "GET",
            signal: controller.signal,
            headers: {
              Accept: "application/json",
            },
          },
        );

        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as
            | { detail?: string | string[] }
            | null;
          const detail = Array.isArray(payload?.detail)
            ? payload.detail.join(" ")
            : payload?.detail;
          throw new Error(detail || `Claim request failed with status ${response.status}.`);
        }

        const payload = (await response.json()) as ClaimDetails;
        if (!controller.signal.aborted) {
          setSelectedClaimDetails(payload);
        }
      } catch (fetchError) {
        if (controller.signal.aborted) {
          return;
        }
        const message =
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load full claim details.";
        setSelectedClaimDetails(null);
        setClaimDetailsError(message);
      } finally {
        if (!controller.signal.aborted) {
          setClaimDetailsLoading(false);
        }
      }
    }

    void loadClaimDetails();

    return () => {
      controller.abort();
    };
  }, [selectedElement]);

  useEffect(() => {
    let disposed = false;

    async function renderGraph() {
      if (!containerRef.current) {
        return;
      }

      if (!graphData || graphData.nodes.length === 0) {
        cytoscapeRef.current?.destroy();
        cytoscapeRef.current = null;
        return;
      }

      const cytoscapeModule = await import("cytoscape/dist/cytoscape.esm.mjs");
      if (disposed || !containerRef.current) {
        return;
      }

      const cytoscape = cytoscapeModule.default;
      cytoscapeRef.current?.destroy();

      const instance = cytoscape({
        container: containerRef.current,
        elements: toCytoscapeElements(graphData),
        layout: {
          name: "cose",
          animate: false,
          padding: 28,
        },
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              "text-wrap": "wrap",
              "text-max-width": "120px",
              "text-valign": "center",
              "text-halign": "center",
              color: "#1f1a14",
              "font-size": "11px",
              "font-weight": 700,
              width: "56px",
              height: "56px",
              "background-color": "#d7b56d",
              "border-width": 2,
              "border-color": "#8f4328",
            },
          },
          {
            selector: 'node[entity_type = "character"]',
            style: {
              "background-color": "#d9875f",
            },
          },
          {
            selector: 'node[entity_type = "location"]',
            style: {
              "background-color": "#88b7a1",
            },
          },
          {
            selector: 'node[entity_type = "concept"]',
            style: {
              "background-color": "#9e8bc9",
            },
          },
          {
            selector: "edge",
            style: {
              width: "2px",
              "curve-style": "bezier",
              "target-arrow-shape": "triangle",
              "target-arrow-color": "#8f4328",
              "line-color": "#8f4328",
              label: "data(label)",
              color: "#5e4e42",
              "font-size": "10px",
              "text-background-color": "#fff8ea",
              "text-background-opacity": 1,
              "text-background-padding": "3px",
            },
          },
          {
            selector: ":selected",
            style: {
              "border-color": "#1e5f74",
              "line-color": "#1e5f74",
              "target-arrow-color": "#1e5f74",
              "background-color": "#f0d17a",
            },
          },
        ],
      }) as unknown as GraphCore;

      instance.on("tap", "node", (event) => {
        const data = (event as { target: { data: () => GraphNode } }).target.data();
        setSelectedElement({ kind: "node", data });
      });

      instance.on("tap", "edge", (event) => {
        const data = (event as { target: { data: () => GraphEdge } }).target.data();
        setSelectedElement({ kind: "edge", data });
      });

      instance.on("tap", (event) => {
        if ((event as { target: unknown }).target === instance) {
          setSelectedElement(null);
          instance.elements().unselect();
        }
      });

      cytoscapeRef.current = instance;
    }

    void renderGraph();

    return () => {
      disposed = true;
    };
  }, [graphData]);

  useEffect(() => {
    return () => {
      cytoscapeRef.current?.destroy();
      cytoscapeRef.current = null;
    };
  }, []);

  function handleFieldChange<K extends keyof FormState>(key: K, value: FormState[K]) {
    setFormState((current) => ({ ...current, [key]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const seedEntityId = formState.seedEntityId.trim();
    if (!seedEntityId) {
      setValidationMessage("Enter a seed entity ID like ENT-0804 before loading the graph.");
      return;
    }

    setValidationMessage(null);
    const params = toApiSearchParams({ ...formState, seedEntityId });
    router.replace(`${pathname}?${params.toString()}`);
  }

  const summary = graphData
    ? `${graphData.nodes.length} node${graphData.nodes.length === 1 ? "" : "s"} · ${graphData.edges.length} edge${graphData.edges.length === 1 ? "" : "s"}`
    : "No graph loaded yet.";

  return (
    <section className="graph-shell">
      <form className="control-panel" onSubmit={handleSubmit}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="seed_entity_id">Seed entity ID</label>
            <input
              id="seed_entity_id"
              name="seed_entity_id"
              placeholder="ENT-0804"
              value={formState.seedEntityId}
              onChange={(event) => handleFieldChange("seedEntityId", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="depth">Depth</label>
            <select
              id="depth"
              name="depth"
              value={formState.depth}
              onChange={(event) => handleFieldChange("depth", event.target.value as "1" | "2")}
            >
              <option value="1">1 hop</option>
              <option value="2">2 hops</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="predicate">Predicate</label>
            <input
              id="predicate"
              name="predicate"
              placeholder="appears_in"
              value={formState.predicate}
              onChange={(event) => handleFieldChange("predicate", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="confidence_min">Confidence min</label>
            <input
              id="confidence_min"
              name="confidence_min"
              inputMode="decimal"
              placeholder="0.6"
              value={formState.confidenceMin}
              onChange={(event) => handleFieldChange("confidenceMin", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="evidence_status">Evidence status</label>
            <input
              id="evidence_status"
              name="evidence_status"
              placeholder="official_confirmed"
              value={formState.evidenceStatus}
              onChange={(event) => handleFieldChange("evidenceStatus", event.target.value)}
            />
          </div>
        </div>
        <div className="actions" style={{ marginTop: 16 }}>
          <button className="primary-button" type="submit" disabled={loading}>
            {loading ? "Loading graph..." : "Load graph"}
          </button>
          <span className="helper-text">Limit is fixed to 100 edges for this first UI pass.</span>
        </div>
        {validationMessage ? <p className="helper-text validation">{validationMessage}</p> : null}
        {error ? <p className="helper-text error-text">{error}</p> : null}
      </form>

      <section className="graph-panel">
        <div className="graph-summary">
          <span className="summary-pill">{summary}</span>
          {graphData ? <span className="summary-pill">Seed: {graphData.seed_entity_id}</span> : null}
          {graphData ? <span className="summary-pill">Depth: {graphData.depth}</span> : null}
        </div>

        {!graphData && !loading && !error ? (
          <div className="notice-panel">
            <p className="muted">
              Load a seed entity to render its graph neighborhood. URL params are preserved so you can share exact graph states later.
            </p>
          </div>
        ) : null}

        {graphData && graphData.nodes.length > 0 && graphData.edges.length === 0 ? (
          <div className="notice-panel">
            <p className="muted">
              The seed node loaded, but no edges matched the current filter set.
            </p>
          </div>
        ) : null}

        <div ref={containerRef} className="graph-stage" />
      </section>

      <section className="detail-panel">
        <h2 className="section-title" style={{ fontSize: "1.6rem" }}>Selection details</h2>
        <div className="detail-grid" style={{ marginTop: 16 }}>
          <article className="detail-card">
            {selectedElement?.kind === "node" ? (
              <>
                <h3>{selectedElement.data.label}</h3>
                <dl className="detail-list">
                  <div>
                    <dt>Entity ID</dt>
                    <dd className="code-line">{selectedElement.data.entity_id}</dd>
                  </div>
                  <div>
                    <dt>Canonical name</dt>
                    <dd>{selectedElement.data.canonical_name}</dd>
                  </div>
                  <div>
                    <dt>Entity type</dt>
                    <dd>{selectedElement.data.entity_type}</dd>
                  </div>
                  <div>
                    <dt>Primary scope game</dt>
                    <dd>{selectedElement.data.primary_scope_game ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Description</dt>
                    <dd>
                      {selectedEntityDetails?.short_description ??
                        selectedElement.data.short_description ??
                        "No description available."}
                    </dd>
                  </div>
                  <div>
                    <dt>Aliases</dt>
                    <dd>
                      {selectedEntityDetails?.aliases?.length
                        ? selectedEntityDetails.aliases.join(", ")
                        : "No aliases available."}
                    </dd>
                  </div>
                  <div>
                    <dt>Notes</dt>
                    <dd>{selectedEntityDetails?.notes ?? "No notes available."}</dd>
                  </div>
                </dl>
                {entityDetailsLoading ? (
                  <p className="muted" style={{ marginTop: 12 }}>
                    Loading full entity details...
                  </p>
                ) : null}
                {entityDetailsError ? (
                  <p className="helper-text error-text" style={{ marginTop: 12 }}>
                    Could not load full entity details. Showing graph metadata only. {entityDetailsError}
                  </p>
                ) : null}
              </>
            ) : selectedElement?.kind === "edge" ? (
              <>
                <h3>{selectedElement.data.predicate}</h3>
                <dl className="detail-list">
                  <div>
                    <dt>Claim ID</dt>
                    <dd className="code-line">{selectedElement.data.claim_id}</dd>
                  </div>
                  <div>
                    <dt>Direction</dt>
                    <dd className="code-line">
                      {selectedClaimDetails?.subject_entity?.canonical_name ??
                        selectedElement.data.source}{" "}
                      →{" "}
                      {selectedClaimDetails?.object_entity?.canonical_name ??
                        selectedElement.data.target}
                    </dd>
                  </div>
                  <div>
                    <dt>Source entity ID</dt>
                    <dd className="code-line">{selectedElement.data.source}</dd>
                  </div>
                  <div>
                    <dt>Target entity ID</dt>
                    <dd className="code-line">{selectedElement.data.target}</dd>
                  </div>
                  <div>
                    <dt>Confidence</dt>
                    <dd>{selectedElement.data.confidence ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Evidence status</dt>
                    <dd>{selectedElement.data.evidence_status ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Source ID</dt>
                    <dd className="code-line">{selectedElement.data.source_id ?? "None"}</dd>
                  </div>
                  <div>
                    <dt>Asset ID</dt>
                    <dd className="code-line">{selectedElement.data.asset_id ?? "None"}</dd>
                  </div>
                  <div>
                    <dt>Claim status</dt>
                    <dd>{selectedElement.data.claim_status ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Locator</dt>
                    <dd>{selectedClaimDetails?.locator ?? "No locator available."}</dd>
                  </div>
                  <div>
                    <dt>Review status</dt>
                    <dd>{selectedClaimDetails?.review_status ?? "No review status available."}</dd>
                  </div>
                  <div>
                    <dt>Note</dt>
                    <dd>{selectedClaimDetails?.note ?? "No note available."}</dd>
                  </div>
                  <div>
                    <dt>Source title</dt>
                    <dd>{selectedClaimDetails?.source?.title ?? "No source title available."}</dd>
                  </div>
                  <div>
                    <dt>Asset description</dt>
                    <dd>
                      {selectedClaimDetails?.asset?.description ?? "No asset description available."}
                    </dd>
                  </div>
                </dl>
                {claimDetailsLoading ? (
                  <p className="muted" style={{ marginTop: 12 }}>
                    Loading full claim details...
                  </p>
                ) : null}
                {claimDetailsError ? (
                  <p className="helper-text error-text" style={{ marginTop: 12 }}>
                    Could not load full claim details. Showing graph metadata only. {claimDetailsError}
                  </p>
                ) : null}
              </>
            ) : (
              <>
                <h3>Nothing selected</h3>
                <p className="muted">
                  Click a node or edge in the graph to inspect its metadata.
                </p>
              </>
            )}
          </article>
        </div>
      </section>
    </section>
  );
}
