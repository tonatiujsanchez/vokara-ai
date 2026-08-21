import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";

import { routes } from "@/routes";

/**
 * A fresh client per test: a cache shared between tests would let one test see
 * another's answer, which is the same lie MSW's `onUnhandledRequest: "error"`
 * exists to prevent.
 */
function testClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

/** Mount one component, for the presentational tests. */
export function renderWithClient(ui: ReactElement): RenderResult {
  return render(<QueryClientProvider client={testClient()}>{ui}</QueryClientProvider>);
}

/**
 * Mount the real route table at one address.
 *
 * The routes are the ones the application ships — a copy of them here would
 * pass while the real table redirected somewhere else.
 */
export function renderAt(path: string): RenderResult {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(
    <QueryClientProvider client={testClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}
