import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "../app/page";

const mockPush = vi.fn();
const FEATURED_ENTITY_LINKS = [
  { name: "Kiana Kaslana", href: "/entities/ENT-0804" },
  { name: "Raiden Shogun", href: "/entities/ENT-0121" },
  { name: "Inazuma", href: "/entities/ENT-0003" },
  { name: "Teyvat", href: "/entities/ENT-0099" },
];

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe("HomePage", () => {
  beforeEach(() => {
    mockPush.mockReset();
  });

  it("introduces the platform and its research purpose", () => {
    render(<HomePage />);

    expect(screen.getByText("Hoyoverse Knowledge Graph")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /explore the connections/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/source-backed knowledge platform/i)).toBeInTheDocument();
  });

  it("renders the global search entry point", () => {
    render(<HomePage />);

    expect(screen.getByLabelText("Search the knowledge graph")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("renders a secondary explore graph action that links to the graph page", () => {
    render(<HomePage />);

    const exploreGraphLink = screen.getByRole("link", { name: "Explore Graph" });

    expect(exploreGraphLink).toBeInTheDocument();
    expect(exploreGraphLink).toHaveAttribute("href", "/graph");
    expect(screen.getByText("Explore relationships visually.")).toBeInTheDocument();
  });

  it("renders curated featured entity entry points", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "Featured entities" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Curated editorial entry points/i),
    ).toBeInTheDocument();

    const featuredLinks = screen
      .getAllByRole("link")
      .filter((link) => link.getAttribute("href")?.startsWith("/entities/"));

    expect(featuredLinks).toHaveLength(FEATURED_ENTITY_LINKS.length);

    for (const entity of FEATURED_ENTITY_LINKS) {
      expect(screen.getByRole("heading", { name: entity.name })).toBeInTheDocument();
      expect(featuredLinks.some((link) => link.getAttribute("href") === entity.href)).toBe(true);
    }
  });

  it("does not render the embedded graph explorer on home", () => {
    render(<HomePage />);

    expect(screen.queryByRole("button", { name: "Load graph" })).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Enter a seed entity ID like ENT-0804 before loading the graph/i),
    ).not.toBeInTheDocument();
  });

  it("navigates to the URL-backed search page when submitted", () => {
    render(<HomePage />);

    fireEvent.change(screen.getByLabelText("Search the knowledge graph"), {
      target: { value: "kiana" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(mockPush).toHaveBeenCalledWith("/search?q=kiana");
  });

  it("submits through the form when Enter is pressed", () => {
    render(<HomePage />);

    const input = screen.getByLabelText("Search the knowledge graph");
    fireEvent.change(input, { target: { value: "kiana" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    fireEvent.submit(input.closest("form")!);

    expect(mockPush).toHaveBeenCalledWith("/search?q=kiana");
  });

  it("trims whitespace before navigating", () => {
    render(<HomePage />);

    fireEvent.change(screen.getByLabelText("Search the knowledge graph"), {
      target: { value: "  Kiana Kaslana  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(mockPush).toHaveBeenCalledWith("/search?q=Kiana%20Kaslana");
  });

  it("does not navigate for a blank query", () => {
    render(<HomePage />);

    fireEvent.change(screen.getByLabelText("Search the knowledge graph"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(mockPush).not.toHaveBeenCalled();
  });
});
