import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SearchPage from "../app/search/page";

const mockPush = vi.fn();
let mockPathname = "/search";
let mockSearchParams = new URLSearchParams();

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

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => mockPathname,
  useSearchParams: () => mockSearchParams,
}));

vi.mock("../lib/api", () => ({
  getApiBaseUrl: () => "http://127.0.0.1:8000",
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

describe("SearchPage", () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockPathname = "/search";
    mockSearchParams = new URLSearchParams();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("renders the basic search controls", () => {
    render(<SearchPage />);

    expect(screen.getByLabelText("Search query")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
    expect(screen.getByLabelText("Entity type")).toBeInTheDocument();
    expect(screen.getByLabelText("Primary scope game")).toBeInTheDocument();
  });

  it("shows validation and does not call fetch for a blank query submission", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<SearchPage />);

    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(
      screen.getByText("Enter a search term before submitting."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders successful search results from a mocked backend response", async () => {
    mockSearchParams = new URLSearchParams({ q: "kiana" });
    mockFetchJson([
      {
        entity_id: "ENT-0804",
        canonical_name: "Kiana Kaslana",
        display_label: "Kiana",
        entity_type: "character",
        primary_scope_game: "Multi",
        aliases: ["Kiana"],
        short_description:
          "Core protagonist identity reused across multiple Honkai continuities.",
        source_count: 2,
      },
    ]);

    render(<SearchPage />);

    expect(await screen.findByText("Kiana")).toBeInTheDocument();
    expect(screen.getByText(/ENT-0804 · character · Multi/)).toBeInTheDocument();
    expect(screen.getByText("Aliases: Kiana")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Core protagonist identity reused across multiple Honkai continuities.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Sources: 2")).toBeInTheDocument();
  });

  it("shows an empty state when the search returns no results", async () => {
    mockSearchParams = new URLSearchParams({ q: "kiana" });
    mockFetchJson([]);

    render(<SearchPage />);

    expect(
      await screen.findByText("No results found. Try a broader query or clear a filter."),
    ).toBeInTheDocument();
  });

  it("shows an error state when the API responds with a failure", async () => {
    mockSearchParams = new URLSearchParams({ q: "kiana" });
    mockFetchJson({ detail: "Backend search failed." }, false, 500);

    render(<SearchPage />);

    expect(await screen.findByText("Backend search failed.")).toBeInTheDocument();
  });

  it("triggers a search on render when q is present in URL params", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
    mockSearchParams = new URLSearchParams({ q: "kiana" });
    vi.stubGlobal("fetch", fetchMock);

    render(<SearchPage />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });
});
