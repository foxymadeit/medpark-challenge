import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";

import "./i18n/i18n";
import "@fontsource-variable/onest";
import "@fontsource-variable/golos-text";
import "@fontsource-variable/geist-mono";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
