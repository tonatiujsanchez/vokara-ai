import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import "@/index.css";
import { router } from "@/routes";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("No se encontró el elemento raíz de la aplicación.");
}

/**
 * One client for the whole SPA.
 *
 * `retry: false` because the API runs on this same machine: a request that
 * fails failed for a reason the user can act on — Docker is down, the provider
 * refused a key — and retrying it silently three times only delays the message
 * that says so (roadmap §11.5).
 */
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
