import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    expect(cytoscapeFactory).toHaveBeenCalledTimes(1);
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
});
