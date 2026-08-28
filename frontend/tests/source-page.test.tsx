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
      file_path_or_url: "https://example.com/evidence/hi3-chapter-1.png",
      locator: "Chapter 1",
      description: "Story evidence screenshot",
      is_primary_evidence: true,
      notes: "Captured from the English client.",
    },
    {
      asset_id: "AST-HI3-0002",
      source_id: "SRC-HI3-0001",
      asset_type: "transcript_excerpt",
      file_path_or_url: "evidence/hi3/chapter-01/transcript.txt",
      locator: "Chapter 1, Scene 3",
      description: "Unreferenced transcript evidence.",
      is_primary_evidence: false,
      notes: null,
    },
    {
      asset_id: "AST-HI3-0003",
      source_id: "SRC-HI3-0001",
      asset_type: "web_archive",
      file_path_or_url: null,
      locator: null,
      description: null,
      is_primary_evidence: null,
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
    {
      claim_id: "CLM-0002",
      subject: {
        entity_id: "ENT-0901",
        canonical_name: "Entity C",
        display_label: null,
        entity_type: "character",
        primary_scope_game: "Honkai Impact 3",
      },
      predicate: "identity_variant",
      object: {
        entity_id: "ENT-0902",
        canonical_name: "Entity D",
        display_label: "Variant D",
        entity_type: "character",
        primary_scope_game: "Honkai Impact 3",
      },
      evidence_status: "editorial_inference",
      confidence: 0.8,
      asset_id: null,
      locator: null,
      note: "Recorded without a source-specific asset.",
      review_status: "draft",
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
    expect(screen.getAllByText("AST-HI3-0001")).toHaveLength(2);
    expect(screen.getByText("Story evidence screenshot")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Supported claims" })).toBeInTheDocument();
    expect(screen.getByText("CLM-0001")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Subject Kiana; relationship Appears in; object Honkai Impact 3"),
    ).toBeInTheDocument();
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

  it("renders every source asset with evidence status and reference behavior", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderSourcePage();

    const evidenceHeading = await screen.findByRole("heading", { name: "Evidence assets" });
    const evidenceSection = evidenceHeading.closest("section");
    if (!evidenceSection) {
      throw new Error("Evidence assets section was not rendered.");
    }

    expect(within(evidenceSection).getAllByRole("heading")).toHaveLength(4);
    expect(within(evidenceSection).getByText("AST-HI3-0001")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("AST-HI3-0002")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("AST-HI3-0003")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Screenshot")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Transcript excerpt")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Web archive")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Chapter 1, Scene 3")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Unreferenced transcript evidence.")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Captured from the English client.")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Primary evidence")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Supporting evidence")).toBeInTheDocument();
    expect(within(evidenceSection).getByText("Evidence status not specified")).toBeInTheDocument();

    const evidenceLink = within(evidenceSection).getByRole("link", { name: "View evidence" });
    expect(evidenceLink).toHaveAttribute("href", "https://example.com/evidence/hi3-chapter-1.png");
    expect(evidenceLink).toHaveAttribute("target", "_blank");
    expect(evidenceLink).toHaveAttribute("rel", "noopener noreferrer");
    expect(
      within(evidenceSection).getByText("evidence/hi3/chapter-01/transcript.txt"),
    ).toBeInTheDocument();
    expect(within(evidenceSection).getAllByRole("link", { name: "View evidence" })).toHaveLength(1);
  });

  it("renders directional source-supported claims and their stored metadata", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderSourcePage();

    const claimsHeading = await screen.findByRole("heading", { name: "Supported claims" });
    const claimsSection = claimsHeading.closest("section");
    if (!claimsSection) {
      throw new Error("Supported claims section was not rendered.");
    }

    expect(within(claimsSection).getByText("CLM-0001")).toBeInTheDocument();
    expect(within(claimsSection).getByText("CLM-0002")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Kiana")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Honkai Impact 3")).toBeInTheDocument();
    expect(within(claimsSection).getByText("ENT-0804")).toBeInTheDocument();
    expect(within(claimsSection).getByText("ENT-0001")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Appears in")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Official confirmed")).toBeInTheDocument();
    expect(within(claimsSection).getByText("1")).toBeInTheDocument();
    expect(within(claimsSection).getByText("AST-HI3-0001")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Chapter 1")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Approved")).toBeInTheDocument();
    expect(within(claimsSection).getAllByText("Active")).toHaveLength(2);
    expect(within(claimsSection).getByText("Identity variant")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Entity C")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Variant D")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Recorded without a source-specific asset.")).toBeInTheDocument();

    const relationships = within(claimsSection).getAllByLabelText(/Subject .* relationship .* object/);
    expect(relationships[0]).toHaveAccessibleName(
      "Subject Kiana; relationship Appears in; object Honkai Impact 3",
    );
    expect(relationships[1]).toHaveAccessibleName(
      "Subject Entity C; relationship Identity variant; object Variant D",
    );
    expect(within(claimsSection).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("preserves subject-to-object claim direction", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      claims: [
        {
          ...sampleDetailResponse.claims[0],
          claim_id: "CLM-0003",
          subject: {
            ...sampleDetailResponse.claims[0].subject,
            entity_id: "ENT-0001",
            canonical_name: "Entity A",
            display_label: "Entity A",
          },
          predicate: "opposes",
          object: {
            ...sampleDetailResponse.claims[0].object,
            entity_id: "ENT-0002",
            canonical_name: "Entity B",
            display_label: "Entity B",
          },
        },
      ],
    });

    await renderSourcePage();

    const relationship = await screen.findByLabelText(
      "Subject Entity A; relationship Opposes; object Entity B",
    );
    expect(relationship).toHaveTextContent("Entity A");
    expect(relationship).toHaveTextContent("Opposes");
    expect(relationship).toHaveTextContent("Entity B");
    expect(relationship).not.toHaveAccessibleName(
      "Subject Entity B; relationship Opposes; object Entity A",
    );
  });

  it("links each claim endpoint to its entity detail route without linking predicates or claims", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderSourcePage();

    const claimsHeading = await screen.findByRole("heading", { name: "Supported claims" });
    const claimsSection = claimsHeading.closest("section");
    if (!claimsSection) {
      throw new Error("Supported claims section was not rendered.");
    }

    expect(within(claimsSection).getByRole("link", { name: "Kiana" })).toHaveAttribute(
      "href",
      "/entities/ENT-0804",
    );
    expect(within(claimsSection).getByRole("link", { name: "Honkai Impact 3" })).toHaveAttribute(
      "href",
      "/entities/ENT-0001",
    );
    expect(within(claimsSection).getByRole("link", { name: "Entity C" })).toHaveAttribute(
      "href",
      "/entities/ENT-0901",
    );
    expect(within(claimsSection).getByRole("link", { name: "Variant D" })).toHaveAttribute(
      "href",
      "/entities/ENT-0902",
    );
    expect(within(claimsSection).queryByRole("link", { name: "Appears in" })).not.toBeInTheDocument();
    expect(within(claimsSection).queryByRole("link", { name: "CLM-0001" })).not.toBeInTheDocument();
    expect(within(claimsSection).getByText("ENT-0804")).toBeInTheDocument();
    expect(within(claimsSection).getByText("ENT-0001")).toBeInTheDocument();
  });

  it("keeps repeated entity occurrences linked to the same entity detail route", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      claims: [
        sampleDetailResponse.claims[0],
        {
          ...sampleDetailResponse.claims[1],
          claim_id: "CLM-0004",
          subject: sampleDetailResponse.claims[0].subject,
        },
      ],
    });

    await renderSourcePage();

    const links = await screen.findAllByRole("link", { name: "Kiana" });
    expect(links).toHaveLength(2);
    links.forEach((link) => expect(link).toHaveAttribute("href", "/entities/ENT-0804"));
  });

  it("renders endpoint labels without malformed links when an entity ID is absent", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      claims: [
        {
          ...sampleDetailResponse.claims[0],
          subject: {
            ...sampleDetailResponse.claims[0].subject,
            entity_id: undefined as unknown as string,
          },
          object: {
            ...sampleDetailResponse.claims[0].object,
            entity_id: null as unknown as string,
          },
        },
      ],
    });

    await renderSourcePage();

    const claimsHeading = await screen.findByRole("heading", { name: "Supported claims" });
    const claimsSection = claimsHeading.closest("section");
    if (!claimsSection) {
      throw new Error("Supported claims section was not rendered.");
    }

    expect(within(claimsSection).getByText("Kiana")).toBeInTheDocument();
    expect(within(claimsSection).getByText("Honkai Impact 3")).toBeInTheDocument();
    expect(within(claimsSection).queryByRole("link", { name: "Kiana" })).not.toBeInTheDocument();
    expect(within(claimsSection).queryByRole("link", { name: "Honkai Impact 3" })).not.toBeInTheDocument();
    expect(within(claimsSection).queryByRole("link", { name: /undefined|null/i })).not.toBeInTheDocument();
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

  it("does not create external links for unsafe source or evidence URLs", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      source: {
        ...sampleDetailResponse.source,
        url: "javascript:alert(1)",
      },
      assets: [
        {
          ...sampleDetailResponse.assets[0],
          file_path_or_url: "data:text/html,test",
        },
      ],
    });

    await renderSourcePage();

    await screen.findByRole("heading", { name: "Source metadata" });
    const metadata = getMetadataSection();
    expect(within(metadata).queryByRole("link", { name: "View original source" })).not.toBeInTheDocument();

    const evidenceHeading = screen.getByRole("heading", { name: "Evidence assets" });
    const evidenceSection = evidenceHeading.closest("section");
    if (!evidenceSection) {
      throw new Error("Evidence assets section was not rendered.");
    }
    expect(within(evidenceSection).getByText("data:text/html,test")).toBeInTheDocument();
    expect(within(evidenceSection).queryByRole("link", { name: "View evidence" })).not.toBeInTheDocument();
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
