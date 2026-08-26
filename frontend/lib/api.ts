const API_PROXY_PATH = "/api";

export function getApiBaseUrl(): string {
  return API_PROXY_PATH;
}

export function buildApiUrl(path: string, params?: URLSearchParams): string {
  const baseUrl = getApiBaseUrl();
  const query = params && params.toString() ? `?${params.toString()}` : "";
  return `${baseUrl}${path}${query}`;
}
