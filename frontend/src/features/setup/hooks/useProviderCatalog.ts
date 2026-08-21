import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { components } from "@/api/schema";

import { unwrap } from "./apiError";

export type ProviderCatalog = components["schemas"]["ProviderCatalogModel"];
export type ProviderOption = components["schemas"]["ProviderOptionModel"];
export type Capability = components["schemas"]["Capability"];

export const catalogKey = ["setup", "providers", "catalog"] as const;

/**
 * The closed list, already resolved by the backend.
 *
 * Two lists and not one, because generation and embeddings are two independent
 * choices (ADR-011), and each option arrives finished — display name, where the
 * key is obtained, default model, estimated cost. The SPA renders what it is
 * given and branches on nothing: adding a provider must not require touching
 * the frontend at all (art. XI).
 */
export function useProviderCatalog(): UseQueryResult<ProviderCatalog, Error> {
  return useQuery({
    queryKey: catalogKey,
    queryFn: () => unwrap(api.GET("/api/v1/setup/providers/catalog")),
  });
}
