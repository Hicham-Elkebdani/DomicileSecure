import { config } from "@/lib/config";
import type { ApiErrorBody } from "@/lib/api/types";

const TOKEN_KEY = "domicilesecure.token";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface StoredToken {
  value: string;
  expiresAt: number;
}

/**
 * Token storage. The token is short-lived (see ACCESS_TOKEN_EXPIRE_MINUTES); moving to an
 * httpOnly cookie + refresh token is listed in docs/security.md as the next hardening step.
 */
export const tokenStore = {
  get(): string | null {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.localStorage.getItem(TOKEN_KEY);
      if (!raw) return null;
      const token = JSON.parse(raw) as StoredToken;
      if (Date.now() >= token.expiresAt) {
        window.localStorage.removeItem(TOKEN_KEY);
        return null;
      }
      return token.value;
    } catch {
      return null;
    }
  },
  set(value: string, expiresInSeconds: number): void {
    const token: StoredToken = { value, expiresAt: Date.now() + expiresInSeconds * 1000 };
    window.localStorage.setItem(TOKEN_KEY, JSON.stringify(token));
  },
  clear(): void {
    window.localStorage.removeItem(TOKEN_KEY);
  },
};

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions extends Omit<RequestInit, "body"> {
  query?: Query;
  json?: unknown;
  body?: BodyInit;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { query, json, headers, ...init } = options;
  const url = new URL(`${config.apiUrl}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }

  const finalHeaders = new Headers(headers);
  const token = tokenStore.get();
  if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  let body = init.body;
  if (json !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  let response: Response;
  try {
    response = await fetch(url, { ...init, headers: finalHeaders, body });
  } catch {
    throw new ApiError(0, "network_error", "Serveur injoignable. Vérifiez que l'API est démarrée.");
  }

  if (response.status === 401 && token) {
    tokenStore.clear();
    onUnauthorized?.();
  }
  if (!response.ok) {
    let payload: ApiErrorBody | null = null;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      response.status,
      payload?.error.code ?? "http_error",
      payload?.error.message ?? `Erreur ${response.status}`,
      payload?.error.details ?? {},
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
