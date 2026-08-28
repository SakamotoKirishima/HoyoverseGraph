import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SourceDetailPage from "../app/sources/[sourceId]/page";

vi.mock("../lib/api", () => ({
  buildApiUrl: (path: string) => `http://127.0.0.1:8000${path}`,
}));

const sampleDetailResponse = {
  source: {
    source_id: "SRC-HI3-0001",
    title: "HI3 Main Story Chapter 1",
    url: null,
    source_type: "official_story",
    source_format: "in_game_text",
    game: "Honkai Impact 3",
    scope: "main_story",
    reliability_tier: "tier_1",
    language: "en",
    publication_date: null,
    notes: null,
  },
  assets: [
    {
      asset_id: "AST-HI3-0001",
      source_id: "SRC-HI3-0001",
      asset_type: "screenshot",
      file_path_or_url: null,
      locator: "Chapter 1",
      description: "Story evidence screenshot",
      is_primary_evidence: true,
      notes: null,
    },
  ],
  claims: [
    {
      claim_id: "CLM-0001",
      subject: {
        entity_id: "ENT-0804",
        canonical_name: "Kiana Kaslana",
        display_label: "Kiana",
        entity_type: "character",
        primary_scope_game: "Multi",
      },
      predicate: "appears_in",
      object: {
        entity_id: "ENT-0001",
        canonical_name: "Honkai Impact 3",
        display_label: "Honkai Impact 3",
        entity_type: "game",
        primary_scope_game: "Honkai Impact 3",
      },
      evidence_status: "official_confirmed",
      confidence: 1,
      asset_id: "AST-HI3-0001",
      locator: "Chapter 1",
      note: null,
      review_status: "approved",
      claim_status: "active",
    },
  ],
  summary: {
    claim_count: 1,
    asset_count: 1,
    primary_evidence_asset_count: 1,
    related_entity_count: 2,
  },
};

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

async function renderSourcePage(sourceId = "SRC-HI3-0001") {
  const page = await SourceDetailPage({ params: Promise.resolve({ sourceId }) });
  return render(page);
}

describe("SourceDetailPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders source metadata, summary counts, assets, and claims", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderSourcePage();

    expect(await screen.findByRole("heading", { name: "HI3 Main Story Chapter 1" })).toBeInTheDocument();
    expect(screen.getByText("SRC-HI3-0001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Summary" })).toBeInTheDocument();
    expect(screen.getByText("Primary evidence assets")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Evidence assets" })).toBeInTheDocument();
    expect(screen.getByText("AST-HI3-0001")).toBeInTheDocument();
    expect(screen.getByText("Story evidence screenshot")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Supported claims" })).toBeInTheDocument();
    expect(screen.getByText("CLM-0001")).toBeInTheDocument();
    expect(screen.getByText(/Kiana.*appears_in.*Honkai Impact 3/)).toBeInTheDocument();
  });

  it("renders explicit empty asset and claim states", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      assets: [],
      claims: [],
      summary: {
        claim_count: 0,
        asset_count: 0,
        primary_evidence_asset_count: 0,
        related_entity_count: 0,
      },
    });

    await renderSourcePage();

    expect(await screen.findByText("No evidence assets are recorded for this source.")).toBeInTheDocument();
    expect(screen.getByText("No claims currently reference this source.")).toBeInTheDocument();
  });

  it("renders a source-not-found state for a 404 response", async () => {
    mockFetchJson({}, false, 404);

    await renderSourcePage("SRC-HI3-9999");

    expect(await screen.findByText("Source not found")).toBeInTheDocument();
    expect(screen.getByText(/No source exists with ID/)).toBeInTheDocument();
  });

  it("renders an invalid source ID state for a 422 response", async () => {
    mockFetchJson({}, false, 422);

    await renderSourcePage("not-a-source");

    expect(await screen.findByText("Invalid source ID")).toBeInTheDocument();
  });

  it("renders a generic error state for failed API requests", async () => {
    mockFetchJson({ detail: "Backend failure" }, false, 500);

    await renderSourcePage();

    expect(await screen.findByText("Unable to load this source")).toBeInTheDocument();
    expect(screen.getByText("Please try again.")).toBeInTheDocument();
  });
});
