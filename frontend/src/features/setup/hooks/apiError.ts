import type { components } from "@/api/schema";

/**
 * The error body, and the closed set of codes, as the backend declares them.
 *
 * Both come from the generated schema and neither is written here (art. I).
 * `ErrorCode` being a union of literals is the point: `contracts/errors.md`
 * says the frontend branches on `code` and on nothing else, so a code renamed
 * in the catalogue has to break this build rather than take a branch that
 * silently never fires again.
 */
export type ApiError = components["schemas"]["Error"];
export type ErrorCode = components["schemas"]["ErrorCode"];

/**
 * A failed call, carrying the body the backend sent.
 *
 * The message is never rewritten on this side: the catalogue owns the wording
 * so that it has a single owner and cannot drift (contracts/errors.md, art. IX).
 */
export class ApiRequestError extends Error {
  constructor(
    readonly body: ApiError,
    readonly status: number,
  ) {
    super(body.message);
    this.name = "ApiRequestError";
  }
}

function isApiError(value: unknown): value is ApiError {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate["code"] === "string" && typeof candidate["message"] === "string";
}

/**
 * The one message the frontend owns, because no backend produced it.
 *
 * When the API does not answer at all there is no `message` to show, and the
 * screen still has to say something true and actionable. Every other text comes
 * from the catalogue.
 */
const UNREACHABLE: ApiError = {
  code: "INTERNAL_ERROR",
  message:
    "No pudimos comunicarnos con el servicio local. Revisa que Docker esté corriendo e " +
    "inténtalo de nuevo.",
};

/**
 * openapi-fetch's `{data, error}` into a value or a throw, for TanStack Query.
 */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await call;
  if (response.ok && data !== undefined) return data;
  throw new ApiRequestError(isApiError(error) ? error : UNREACHABLE, response.status);
}

/** The code of a failed mutation, for the callers that branch on one. */
export function codeOf(error: unknown): ErrorCode | null {
  return error instanceof ApiRequestError ? error.body.code : null;
}

/** The message to put on screen, whatever went wrong. */
export function messageOf(error: unknown): string {
  return error instanceof ApiRequestError ? error.body.message : UNREACHABLE.message;
}
