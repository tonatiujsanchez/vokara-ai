import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { ReadyScreen } from "@/features/onboarding/ReadyScreen";
import { DisclosureScreen } from "@/features/setup/disclosure/DisclosureScreen";
import { EmailScreen } from "@/features/setup/email/EmailScreen";
import { ProvidersScreen } from "@/features/setup/providers/ProvidersScreen";
import { StatusScreen } from "@/features/status/StatusScreen";
import { FirstRunEntry, FirstRunGuard } from "@/routes/FirstRunGuard";

/**
 * The routes, exported apart from the router so tests can mount them in memory.
 *
 * `/` resolves instead of rendering: on a fresh installation the first thing
 * anyone sees is the disclosure, and after the first run it is the onboarding
 * (FR-001, FR-015). The diagnostics screen keeps its own address because error
 * messages send people to it by name (contracts/errors.md).
 */
export const routes: RouteObject[] = [
  { path: "/", element: <FirstRunEntry /> },
  {
    element: <FirstRunGuard requires={{ kind: "step", step: "disclosure" }} />,
    children: [{ path: "/setup/disclosure", element: <DisclosureScreen /> }],
  },
  {
    element: <FirstRunGuard requires={{ kind: "step", step: "providers" }} />,
    children: [{ path: "/setup/providers", element: <ProvidersScreen /> }],
  },
  {
    element: <FirstRunGuard requires={{ kind: "step", step: "email" }} />,
    children: [{ path: "/setup/email", element: <EmailScreen /> }],
  },
  {
    element: <FirstRunGuard requires={{ kind: "complete" }} />,
    children: [{ path: "/onboarding", element: <ReadyScreen /> }],
  },
  { path: "/status", element: <StatusScreen /> },
];

export const router = createBrowserRouter(routes);
