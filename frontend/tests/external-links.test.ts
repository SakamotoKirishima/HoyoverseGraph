import { describe, expect, it } from "vitest";

import { isHttpUrl } from "../lib/external-links";

describe("isHttpUrl", () => {
  it.each([
    "https://example.com",
    "http://example.com",
    "https://example.com/path?q=value#section",
  ])("accepts supported HTTP URLs", (value) => {
    expect(isHttpUrl(value)).toBe(true);
  });

  it.each([
    "javascript:alert(1)",
    "data:text/html,test",
    "file:///tmp/test",
    "ftp://example.com",
    "/local/path",
    "evidence/test.png",
    "httpwhatever",
    "",
    "   ",
    null,
    undefined,
  ])("rejects unsupported URL values", (value) => {
    expect(isHttpUrl(value)).toBe(false);
  });
});
