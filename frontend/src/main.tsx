import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";

import { router } from "@/routes";
import "@/index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("No se encontró el elemento raíz de la aplicación.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
