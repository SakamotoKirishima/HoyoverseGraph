const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

function getApiBaseUrl(): string {
  if (!API_BASE_URL) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not configured. Add it to frontend/.env.local or your environment.",
    );
  }
  return API_BASE_URL.replace(/\/$/, "");
}

export function buildApiUrl(path: string, params?: URLSearchParams): string {
  const baseUrl = getApiBaseUrl();
  const query = params && params.toString() ? `?${params.toString()}` : "";
  return `${baseUrl}${path}${query}`;
}
