import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EntityDetailPage from "../app/entities/[entityId]/page";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: ReactNode;
    href: string;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("../lib/api", () => ({
  buildApiUrl: (path: string) => `http://127.0.0.1:8000${path}`,
}));

const sampleDetailResponse = {
  entity: {
    entity_id: "ENT-0804",
    canonical_name: "Kiana Kaslana",
    display_label: "Kiana",
    entity_type: "character",
    primary_scope_game: "Multi",
    aliases: ["Kiana"],
    short_description:
      "Core protagonist identity reused across multiple Honkai continuities.",
    starter_status: "seed",
    notes: "Editorial family anchor.",
  },
  claims: [
    {
      claim_id: "CLM-0001",
      subject_entity_id: "ENT-0804",
      predicate: "identity_variant",
      object_entity_id: "ENT-0201",
      evidence_status: "editorial_inference",
      confidence: 0.8,
      source_id: "SRC-INT-0001",
      asset_id: "AST-INT-0001",
      locator: "Internal mapping note",
      note: "Kiana assigned to editorial family.",
      review_status: "draft",
      claim_status: "active",
      supersedes_claim_id: null,
      contradicts_claim_id: null,
      direction: "outgoing" as const,
    },
    {
      claim_id: "CLM-0002",
      subject_entity_id: "ENT-0201",
      predicate: "identity_variant",
      object_entity_id: "ENT-0804",
      evidence_status: null,
      confidence: null,
      source_id: null,
      asset_id: null,
      locator: null,
      note: null,
      review_status: null,
      claim_status: "draft",
      supersedes_claim_id: null,
      contradicts_claim_id: null,
      direction: "incoming" as const,
    },
  ],
  sources: [
    {
      source_id: "SRC-INT-0001",
      title: "Internal Editorial Mapping",
      url: "https://example.com/internal-mapping",
      source_type: "internal_editorial",
      source_format: "internal_note",
      game: "Multi",
      scope: "identity_mapping",
      reliability_tier: "tier_4",
      language: "en",
      publication_date: null,
      notes: "Used for internal family groupings.",
    },
  ],
  assets: [
    {
      asset_id: "AST-INT-0001",
      source_id: "SRC-INT-0001",
      asset_type: "document",
      file_path_or_url: "https://example.com/assets/internal-mapping.pdf",
      locator: "Appendix A",
      description: "Supporting mapping extract",
      is_primary_evidence: true,
      notes: "Internal attachment",
    },
  ],
  graph_context: {
    seed_entity_id: "ENT-0804",
    graph_url: "/graph?seed_entity_id=ENT-0804&depth=1",
    related_claim_count: 2,
    related_entity_count: 1,
    source_count: 1,
    asset_count: 1,
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

async function renderEntityPage(entityId = "ENT-0804") {
  const page = await EntityDetailPage({
    params: Promise.resolve({ entityId }),
  });
  return render(page);
}

describe("EntityDetailPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders canonical metadata from a successful detail response", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderEntityPage();

    expect(await screen.findByRole("heading", { name: "Kiana" })).toBeInTheDocument();
    expect(screen.getByText("Kiana Kaslana")).toBeInTheDocument();
    expect(screen.getAllByText("ENT-0804").length).toBeGreaterThan(0);
    expect(screen.getByText("character")).toBeInTheDocument();
    expect(screen.getAllByText("Multi").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "Core protagonist identity reused across multiple Honkai continuities.",
      ),
    ).toBeInTheDocument();
  });

  it("renders aliases, claims, sources, assets, graph links, and provenance details", async () => {
    mockFetchJson(sampleDetailResponse);

    await renderEntityPage();

    expect(await screen.findByText("Aliases (1)")).toBeInTheDocument();
    expect(screen.getAllByText("Kiana").length).toBeGreaterThan(0);

    expect(screen.getByText("Related Claims (2)")).toBeInTheDocument();
    expect(screen.getAllByText("CLM-0001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CLM-0002").length).toBeGreaterThan(0);
    expect(screen.getAllByText("identity_variant").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Outgoing:/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Incoming:/).length).toBeGreaterThan(0);

    expect(screen.getByText("Related Sources (1)")).toBeInTheDocument();
    expect(screen.getAllByText("Internal Editorial Mapping").length).toBeGreaterThan(0);
    const sourceLink = screen.getAllByRole("link", {
      name: "https://example.com/internal-mapping",
    })[0];
    expect(sourceLink).toHaveAttribute("href", "https://example.com/internal-mapping");

    expect(screen.getByText("Linked Evidence Assets (1)")).toBeInTheDocument();
    expect(screen.getAllByText("AST-INT-0001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("document").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Yes").length).toBeGreaterThan(0);

    const graphLink = screen.getByRole("link", { name: "View 1-hop graph" });
    expect(graphLink).toHaveAttribute("href", "/graph?seed_entity_id=ENT-0804&depth=1");
    expect(screen.getByRole("link", { name: "View 2-hop graph" })).toHaveAttribute(
      "href",
      "/graph?seed_entity_id=ENT-0804&depth=2",
    );

    expect(screen.getByText("Evidence & Provenance")).toBeInTheDocument();
    expect(screen.getAllByText("Source record").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Evidence asset").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Supporting mapping extract").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No source linked.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No evidence asset linked.").length).toBeGreaterThan(0);
  });

  it("shows the empty alias state when no aliases are present", async () => {
    mockFetchJson({
      ...sampleDetailResponse,
      entity: {
        ...sampleDetailResponse.entity,
        aliases: [],
      },
    });

    await renderEntityPage();

    expect(await screen.findByText("Aliases (0)")).toBeInTheDocument();
    expect(screen.getByText("No aliases listed.")).toBeInTheDocument();
  });

  it("shows a not-found state for a 404 detail response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
      }),
    );

    await renderEntityPage();

    expect(await screen.findByText("Entity not found")).toBeInTheDocument();
    expect(
      screen.getByText(/No entity detail record was found for/),
    ).toBeInTheDocument();
  });

  it("shows an API error state for a non-OK detail response", async () => {
    mockFetchJson({ detail: "Backend entity detail failed." }, false, 500);

    await renderEntityPage();

    expect(await screen.findByText("Could not load entity details")).toBeInTheDocument();
    expect(screen.getByText("Backend entity detail failed.")).toBeInTheDocument();
  });

  it("shows a generic error state when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Network exploded.")));

    await renderEntityPage();

    expect(await screen.findByText("Could not load entity details")).toBeInTheDocument();
    expect(screen.getByText("Network exploded.")).toBeInTheDocument();
  });
});
