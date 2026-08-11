import createClient from "openapi-fetch";

import type { paths } from "@/api/schema";

/**
 * The only way the frontend talks to the API.
 *
 * Typed against schema.d.ts, which is generated from the backend's OpenAPI.
 * Writing an API type by hand here is forbidden (art. I): rename a field in a
 * Pydantic model, regenerate, and this build breaks — which is the point.
 *
 * The base URL is relative: the SPA and the API are served from the same
 * origin, and in development Vite proxies /api (see vite.config.ts).
 */
export const api = createClient<paths>({ baseUrl: "/" });
