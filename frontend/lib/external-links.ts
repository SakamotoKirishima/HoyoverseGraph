export function isHttpUrl(value: string | null | undefined): value is string {
  if (typeof value !== "string" || !value.trim() || value.trim() !== value) {
    return false;
  }

  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
