import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "flag-icons/css/flag-icons.min.css";
import "./index.css";
import App from "./App";
import { SystemActionsProvider } from "./contexts/SystemActions";
import { I18nProvider } from "./i18n";
import { exposePluginSDK } from "./plugins";
import { ThemeProvider } from "./themes";
import { HERMES_BASE_PATH } from "./lib/api";

function disableBrowserTranslation() {
  document.documentElement.lang = "zh-CN";
  document.documentElement.setAttribute("translate", "no");
  document.documentElement.classList.add("notranslate");
  document.body?.setAttribute("translate", "no");
  document.body?.classList.add("notranslate");

  const root = document.getElementById("root");
  root?.setAttribute("translate", "no");
  root?.classList.add("notranslate");

  if (!document.querySelector('meta[name="google"][content="notranslate"]')) {
    const meta = document.createElement("meta");
    meta.name = "google";
    meta.content = "notranslate";
    document.head.appendChild(meta);
  }
}

// Expose the plugin SDK before rendering so plugins loaded via <script>
// can access React, components, etc. immediately.
exposePluginSDK();
disableBrowserTranslation();

createRoot(document.getElementById("root")!).render(
  <BrowserRouter basename={HERMES_BASE_PATH || undefined}>
    <I18nProvider>
      <ThemeProvider>
        <SystemActionsProvider>
          <App />
        </SystemActionsProvider>
      </ThemeProvider>
    </I18nProvider>
  </BrowserRouter>,
);
