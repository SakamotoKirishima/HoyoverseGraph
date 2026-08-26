import type { ReactNode } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "../app/page";

const mockPush = vi.fn();

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

  it("renders the global search entry point", () => {
    render(<HomePage />);

    expect(screen.getByLabelText("Search the knowledge graph")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
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
