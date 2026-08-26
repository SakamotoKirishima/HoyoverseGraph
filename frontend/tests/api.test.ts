import { describe, expect, it } from "vitest";

import { buildApiUrl, getApiBaseUrl } from "../lib/api";

describe("API URL helpers", () => {
  it("uses the same-origin API proxy path", () => {
    expect(getApiBaseUrl()).toBe("/api");
    expect(buildApiUrl("/search", new URLSearchParams({ q: "kiana" }))).toBe(
      "/api/search?q=kiana",
    );
  });
});
