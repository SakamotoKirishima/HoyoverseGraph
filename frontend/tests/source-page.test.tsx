import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SourceDetailPage from "../app/sources/[sourceId]/page";

vi.mock("../lib/api", () => ({
  buildApiUrl: (path: string) => `http://127.0.0.1:8000${path}`,
}));

const sampleDetailResponse = {
  source: {
    source_id: "SRC-HI3-0001",
    title: "HI3 Main Story Chapter 1",
    url: "https://example.com/hi3/chapter-1",
    source_type: "official_story",
    source_format: "in_game_text",
    game: "Honkai Impact 3",
    scope: "main_story",
    reliability_tier: "tier_1",
    language: "en",
    publication_date: "2023-07-18",
    notes: "Primary canon source with scene-level references.",
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

function getMetadataSection(): HTMLElement {
  const heading = screen.getByRole("heading", { name: "Source metadata" });
  const section = heading.closest("section");
  if (!section) {
    throw new Error("Source metadata section was not rendered.");
  }
  return section;
}

function getMetadataValue(section: HTMLElement, label: string): HTMLElement | null {
  const term = within(section).getByText(label);
  return term.nextElementSibling as HTMLElement | null;
}

describe("SourceDetailPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders source metadata, summary counts, assets, and claims", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderSourcePage();

    expect(await screen.findByRole("heading", { name: "HI3 Main Story Chapter 1" })).toBeInTheDocument();
    expect(screen.getAllByText("SRC-HI3-0001")).toHaveLength(2);
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

  it("renders formatted canonical metadata, the original URL, and notes", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderSourcePage();

    await screen.findByRole("heading", { name: "Source metadata" });
    const metadata = getMetadataSection();
    expect(getMetadataValue(metadata, "Source ID")).toHaveTextContent("SRC-HI3-0001");
    expect(getMetadataValue(metadata, "Source type")).toHaveTextContent("Official story");
    expect(getMetadataValue(metadata, "Source format")).toHaveTextContent("In game text");
    expect(getMetadataValue(metadata, "Game")).toHaveTextContent("Honkai Impact 3");
    expect(getMetadataValue(metadata, "Scope")).toHaveTextContent("Main story");
    expect(getMetadataValue(metadata, "Reliability tier")).toHaveTextContent("Tier 1");
    expect(getMetadataValue(metadata, "Language")).toHaveTextContent("en");
    expect(getMetadataValue(metadata, "Publication date")).toHaveTextContent("Jul 18, 2023");
    expect(getMetadataValue(metadata, "Notes")).toHaveTextContent(
      "Primary canon source with scene-level references.",
    );

    const sourceLink = within(metadata).getByRole("link", { name: "View original source" });
    expect(sourceLink).toHaveAttribute("href", "https://example.com/hi3/chapter-1");
    expect(sourceLink).toHaveAttribute("target", "_blank");
    expect(sourceLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("uses a neutral placeholder for nullable metadata and omits a null URL", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      source: {
        ...sampleDetailResponse.source,
        url: null,
        game: null,
        scope: null,
        reliability_tier: null,
        language: null,
        publication_date: null,
        notes: null,
      },
    });

    await renderSourcePage();

    await screen.findByRole("heading", { name: "Source metadata" });
    const metadata = getMetadataSection();
    expect(getMetadataValue(metadata, "Game")).toHaveTextContent("—");
    expect(getMetadataValue(metadata, "Scope")).toHaveTextContent("—");
    expect(getMetadataValue(metadata, "Reliability tier")).toHaveTextContent("—");
    expect(getMetadataValue(metadata, "Language")).toHaveTextContent("—");
    expect(getMetadataValue(metadata, "Publication date")).toHaveTextContent("—");
    expect(getMetadataValue(metadata, "Notes")).toHaveTextContent("—");
    expect(within(metadata).queryByRole("link", { name: "View original source" })).not.toBeInTheDocument();
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
