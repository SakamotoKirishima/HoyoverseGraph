import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GraphPage from "../app/graph/page";

const mockReplace = vi.fn();
let mockPathname = "/graph";
let mockSearchParams = new URLSearchParams();

type CytoscapeInstance = {
  on: ReturnType<typeof vi.fn>;
  elements: () => { unselect: ReturnType<typeof vi.fn> };
  destroy: ReturnType<typeof vi.fn>;
};

const cytoscapeFactory = vi.fn((): CytoscapeInstance => ({
  on: vi.fn(),
  elements: () => ({ unselect: vi.fn() }),
  destroy: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
  }),
  usePathname: () => mockPathname,
  useSearchParams: () => mockSearchParams,
}));

vi.mock("../lib/api", () => ({
  buildApiUrl: (path: string, params?: URLSearchParams) => {
    const query = params && params.toString() ? `?${params.toString()}` : "";
    return `http://127.0.0.1:8000${path}${query}`;
  },
}));

vi.mock("cytoscape/dist/cytoscape.esm.mjs", () => ({
  default: cytoscapeFactory,
}));

function mockFetchJson(data: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      json: async () => data,
    }),
  );
}

function mockFetchSequence(...responses: unknown[]) {
  const fetchMock = vi.fn().mockImplementation(async () => ({
    ok: true,
    status: 200,
    json: async () => responses.shift(),
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function selectGraphEdge(edge: Record<string, unknown>) {
  await waitFor(() => expect(cytoscapeFactory).toHaveBeenCalled());
  const instance = cytoscapeFactory.mock.results.at(-1)?.value;
  const handler = instance?.on.mock.calls.find(
    ([eventName, selector]) => eventName === "tap" && selector === "edge",
  )?.[2] as ((event: { target: { data: () => Record<string, unknown> } }) => void) | undefined;

  if (!handler) {
    throw new Error("Graph edge selection handler was not registered.");
  }

  act(() => {
    handler({ target: { data: () => edge } });
  });
}

function graphResponse(edges: Record<string, unknown>[]) {
  return {
    seed_entity_id: "ENT-0804",
    depth: 1,
    nodes: [
      {
        id: "ENT-0804",
        entity_id: "ENT-0804",
        label: "Kiana",
        canonical_name: "Kiana Kaslana",
        entity_type: "character",
        primary_scope_game: "Multi",
        short_description: "Core protagonist identity.",
      },
      {
        id: "ENT-0001",
        entity_id: "ENT-0001",
        label: "Honkai Impact 3",
        canonical_name: "Honkai Impact 3",
        entity_type: "game",
        primary_scope_game: "Honkai Impact 3",
        short_description: "Game title.",
      },
    ],
    edges,
  };
}

function claimDetails({
  claimId,
  sourceId,
  sourceTitle,
}: {
  claimId: string;
  sourceId: string | null;
  sourceTitle: string | null;
}) {
  return {
    claim_id: claimId,
    subject_entity_id: "ENT-0804",
    predicate: "appears_in",
    object_entity_id: "ENT-0001",
    evidence_status: "official_confirmed",
    confidence: 1,
    source_id: sourceId,
    asset_id: "AST-HI3-0001",
    locator: "Chapter 1",
    note: null,
    review_status: "approved",
    claim_status: "active",
    supersedes_claim_id: null,
    contradicts_claim_id: null,
    subject_entity: {
      entity_id: "ENT-0804",
      canonical_name: "Kiana Kaslana",
    },
    object_entity: {
      entity_id: "ENT-0001",
      canonical_name: "Honkai Impact 3",
    },
    source: sourceId ? { source_id: sourceId, title: sourceTitle } : null,
    asset: { asset_id: "AST-HI3-0001", description: "Story evidence screenshot" },
  };
}

describe("GraphPage", () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockPathname = "/graph";
    mockSearchParams = new URLSearchParams();
    cytoscapeFactory.mockClear();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders the basic graph controls", () => {
    render(<GraphPage />);

    expect(screen.getByLabelText("Seed entity ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Depth")).toBeInTheDocument();
    expect(screen.getByLabelText("Predicate")).toBeInTheDocument();
    expect(screen.getByLabelText("Confidence min")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence status")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load graph" })).toBeInTheDocument();
  });

  it("shows validation and does not call fetch for a blank seed submission", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<GraphPage />);

    fireEvent.click(screen.getByRole("button", { name: "Load graph" }));

    expect(
      screen.getByText("Enter a seed entity ID like ENT-0804 before loading the graph."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders graph summary details from a mocked backend response", async () => {
    mockSearchParams = new URLSearchParams({
      seed_entity_id: "ENT-0804",
      depth: "1",
    });
    mockFetchJson({
      seed_entity_id: "ENT-0804",
      depth: 1,
      nodes: [
        {
          id: "ENT-0804",
          entity_id: "ENT-0804",
          label: "Kiana",
          canonical_name: "Kiana Kaslana",
          entity_type: "character",
          primary_scope_game: "Multi",
          short_description:
            "Core protagonist identity reused across multiple Honkai continuities.",
        },
        {
          id: "ENT-0001",
          entity_id: "ENT-0001",
          label: "Honkai Impact 3",
          canonical_name: "Honkai Impact 3",
          entity_type: "game",
          primary_scope_game: "Honkai Impact 3",
          short_description: "Game title.",
        },
      ],
      edges: [
        {
          id: "CLM-0001",
          claim_id: "CLM-0001",
          source: "ENT-0804",
          target: "ENT-0001",
          predicate: "appears_in",
          confidence: 0.9,
          evidence_status: "official_confirmed",
          source_id: "SRC-HI3-0001",
          asset_id: null,
          claim_status: "active",
        },
      ],
    });

    render(<GraphPage />);

    expect(
      await screen.findByText("2 nodes · 1 edge", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByText("Seed: ENT-0804")).toBeInTheDocument();
    expect(screen.getByText("Depth: 1")).toBeInTheDocument();
    await waitFor(() => {
      expect(cytoscapeFactory).toHaveBeenCalledTimes(1);
    });
  });

  it("shows the no-edges state when only the seed node is returned", async () => {
    mockSearchParams = new URLSearchParams({
      seed_entity_id: "ENT-0804",
      depth: "1",
    });
    mockFetchJson({
      seed_entity_id: "ENT-0804",
      depth: 1,
      nodes: [
        {
          id: "ENT-0804",
          entity_id: "ENT-0804",
          label: "Kiana",
          canonical_name: "Kiana Kaslana",
          entity_type: "character",
          primary_scope_game: "Multi",
          short_description:
            "Core protagonist identity reused across multiple Honkai continuities.",
        },
      ],
      edges: [],
    });

    render(<GraphPage />);

    expect(
      await screen.findByText(
        "The seed node loaded, but no edges matched the current filter set.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("1 node · 0 edges", { exact: false })).toBeInTheDocument();
  });

  it("shows an error state when the API responds with a failure", async () => {
    mockSearchParams = new URLSearchParams({
      seed_entity_id: "ENT-0804",
      depth: "1",
    });
    mockFetchJson({ detail: "Graph backend failed." }, false, 500);

    render(<GraphPage />);

    expect(await screen.findByText("Graph backend failed.")).toBeInTheDocument();
  });

  it("triggers a graph load on render when URL params include a seed entity", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        seed_entity_id: "ENT-0804",
        depth: 1,
        nodes: [
          {
            id: "ENT-0804",
            entity_id: "ENT-0804",
            label: "Kiana",
            canonical_name: "Kiana Kaslana",
            entity_type: "character",
            primary_scope_game: "Multi",
            short_description:
              "Core protagonist identity reused across multiple Honkai continuities.",
          },
        ],
        edges: [],
      }),
    });
    mockSearchParams = new URLSearchParams({
      seed_entity_id: "ENT-0804",
      depth: "1",
      predicate: "appears_in",
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<GraphPage />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
    expect(fetchMock.mock.calls[0]?.[0]).toContain("/graph?");
    expect(fetchMock.mock.calls[0]?.[0]).toContain("seed_entity_id=ENT-0804");
    expect(fetchMock.mock.calls[0]?.[0]).toContain("predicate=appears_in");
  });

  it("links a selected claim source title to Source Detail and keeps its ID visible", async () => {
    mockSearchParams = new URLSearchParams({ seed_entity_id: "ENT-0804", depth: "1" });
    const edge = {
      id: "CLM-0001",
      claim_id: "CLM-0001",
      source: "ENT-0804",
      target: "ENT-0001",
      predicate: "appears_in",
      confidence: 1,
      evidence_status: "official_confirmed",
      source_id: "SRC-HI3-0001",
      asset_id: "AST-HI3-0001",
      claim_status: "active",
    };
    const fetchMock = mockFetchSequence(
      graphResponse([edge]),
      claimDetails({
        claimId: "CLM-0001",
        sourceId: "SRC-HI3-0001",
        sourceTitle: "HI3 Main Story Chapter 1",
      }),
    );

    render(<GraphPage />);
    await selectGraphEdge(edge);

    const sourceLink = await screen.findByRole("link", { name: "HI3 Main Story Chapter 1" });
    expect(sourceLink).toHaveAttribute("href", "/sources/SRC-HI3-0001");
    expect(sourceLink).not.toHaveAttribute("target", "_blank");
    expect(screen.getByText("SRC-HI3-0001")).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain("/sources/SRC-HI3-0001");
  });

  it("uses a source ID as the link text when graph claim details have no title", async () => {
    mockSearchParams = new URLSearchParams({ seed_entity_id: "ENT-0804", depth: "1" });
    const edge = {
      id: "CLM-0002",
      claim_id: "CLM-0002",
      source: "ENT-0804",
      target: "ENT-0001",
      predicate: "appears_in",
      confidence: 1,
      evidence_status: "official_confirmed",
      source_id: "SRC-HI3-0002",
      asset_id: null,
      claim_status: "active",
    };
    mockFetchSequence(
      graphResponse([edge]),
      claimDetails({ claimId: "CLM-0002", sourceId: "SRC-HI3-0002", sourceTitle: null }),
    );

    render(<GraphPage />);
    await selectGraphEdge(edge);

    const sourceLink = await screen.findByRole("link", { name: "SRC-HI3-0002" });
    expect(sourceLink).toHaveAttribute("href", "/sources/SRC-HI3-0002");
  });

  it("keeps graph claims separate when their selected sources differ", async () => {
    mockSearchParams = new URLSearchParams({ seed_entity_id: "ENT-0804", depth: "1" });
    const firstEdge = {
      id: "CLM-0001",
      claim_id: "CLM-0001",
      source: "ENT-0804",
      target: "ENT-0001",
      predicate: "appears_in",
      confidence: 1,
      evidence_status: "official_confirmed",
      source_id: "SRC-HI3-0001",
      asset_id: null,
      claim_status: "active",
    };
    const secondEdge = {
      ...firstEdge,
      id: "CLM-0002",
      claim_id: "CLM-0002",
      source_id: "SRC-WIKI-0001",
    };
    mockFetchSequence(
      graphResponse([firstEdge, secondEdge]),
      claimDetails({ claimId: "CLM-0001", sourceId: "SRC-HI3-0001", sourceTitle: "Story One" }),
      claimDetails({ claimId: "CLM-0002", sourceId: "SRC-WIKI-0001", sourceTitle: "Wiki Entry" }),
    );

    render(<GraphPage />);
    await selectGraphEdge(firstEdge);
    expect((await screen.findByRole("link", { name: "Story One" }))).toHaveAttribute(
      "href",
      "/sources/SRC-HI3-0001",
    );

    await selectGraphEdge(secondEdge);
    expect((await screen.findByRole("link", { name: "Wiki Entry" }))).toHaveAttribute(
      "href",
      "/sources/SRC-WIKI-0001",
    );
  });

  it("does not render a malformed source link when a selected claim has no source ID", async () => {
    mockSearchParams = new URLSearchParams({ seed_entity_id: "ENT-0804", depth: "1" });
    const edge = {
      id: "CLM-0003",
      claim_id: "CLM-0003",
      source: "ENT-0804",
      target: "ENT-0001",
      predicate: "appears_in",
      confidence: null,
      evidence_status: null,
      source_id: null,
      asset_id: null,
      claim_status: "active",
    };
    mockFetchSequence(
      graphResponse([edge]),
      claimDetails({ claimId: "CLM-0003", sourceId: null, sourceTitle: null }),
    );

    render(<GraphPage />);
    await selectGraphEdge(edge);

    expect(await screen.findByText("No source linked.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /undefined|null/i })).not.toBeInTheDocument();
  });
});
