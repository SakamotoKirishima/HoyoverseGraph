import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function DummyComponent() {
  return <p>Frontend test setup is working.</p>;
}

describe("frontend testing setup", () => {
  it("renders a simple component", () => {
    render(<DummyComponent />);

    expect(screen.getByText("Frontend test setup is working.")).toBeInTheDocument();
  });
});
