export function getApiBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!baseUrl) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not configured. Add it to frontend/.env.local or your environment.",
    );
  }
  return baseUrl.replace(/\/+$/, "");
}
