export const EMPTY_DETAIL_VALUE = "—";

export function formatEnumValue(value: string | null): string {
  if (!value?.trim()) {
    return EMPTY_DETAIL_VALUE;
  }

  const normalized = value.replaceAll("_", " ").trim().toLowerCase();
  return `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}`;
}

export function formatOptionalValue(value: string | null): string {
  return value?.trim() || EMPTY_DETAIL_VALUE;
}
