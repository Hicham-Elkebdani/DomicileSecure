/**
 * Public runtime configuration. NEXT_PUBLIC_* variables are inlined at build time,
 * so they must never contain secrets.
 */
const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(
  /\/$/,
  "",
);

export const config = {
  apiUrl,
  wsUrl: process.env.NEXT_PUBLIC_WS_URL ?? `${apiUrl.replace(/^http/, "ws")}/ws`,
} as const;
