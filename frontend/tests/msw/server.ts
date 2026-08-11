import { setupServer } from "msw/node";

/**
 * Every handler mocks the API against the generated OpenAPI schema, never
 * against hand written shapes (art. I). Handlers live next to the test that
 * needs them and are installed with `server.use(...)`.
 */
export const server = setupServer();
