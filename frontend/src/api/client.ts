import createClient from "openapi-fetch";

import type { paths } from "@/api/schema";

/**
 * The only way the frontend talks to the API.
 *
 * Typed against schema.d.ts, which is generated from the backend's OpenAPI.
 * Writing an API type by hand here is forbidden (art. I): rename a field in a
 * Pydantic model, regenerate, and this build breaks — which is the point.
 *
 * The base URL is the page's own origin: the SPA and the API are served
 * together, and in development Vite proxies /api (see vite.config.ts). It is
 * spelled out rather than left relative because fetch outside a browser — a
 * jsdom test — rejects a relative URL.
 */
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Resolved on every call instead of captured at module load, so a test that
  // installs its interceptor afterwards still sees the request.
  fetch: (request) => globalThis.fetch(request),
});
