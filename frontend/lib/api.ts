const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" &&
  window.location.hostname !== "localhost" &&
  window.location.hostname !== "127.0.0.1"
    ? "/api/v1"
    : "http://localhost:8000/api/v1");

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("truthshield_token");
}

export function setAuthToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("truthshield_token", token);
  }
}

export function clearAuthToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("truthshield_token");
    localStorage.removeItem("truthshield_user");
  }
}

export async function apiFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401 && typeof window !== "undefined") {
    clearAuthToken();
  }

  return response;
}
