import { createBrowserRouter } from "react-router-dom";

import { StatusScreen } from "@/features/status/StatusScreen";

/**
 * The first-run guard arrives in T066: it will keep /onboarding unreachable
 * while pending_step is not null (FR-002, FR-010). That guard is a convenience;
 * the real gate is on the server.
 */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <StatusScreen />,
  },
]);
