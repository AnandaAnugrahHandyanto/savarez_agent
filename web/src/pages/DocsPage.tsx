import { useLayoutEffect } from "react";
import { ExternalLink } from "lucide-react";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";
import { PluginSlot } from "@/plugins";

import { Card } from "@/components/ui/card";

export const HERMES_DOCS_URL = "https://hermes-agent.nousresearch.com/docs/";

const DS_BUTTON_OUTLINED_LINK_CN = cn(
  "group relative inline-grid grid-cols-[auto_1fr_auto] items-center",
  "px-3.5 py-2 gap-2",
  "leading-0 font-bold tracking-[0.15em] uppercase text-[10px]",
  "text-midground bg-background/40 backdrop-blur-md border border-border/50",
  "hover:bg-background/60 transition-colors",
);

export default function DocsPage() {
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  useLayoutEffect(() => {
    setEnd(
      <a
        href={HERMES_DOCS_URL}
        target="_blank"
        rel="noopener noreferrer"
        className={DS_BUTTON_OUTLINED_LINK_CN}
      >
        <ExternalLink className="size-3" />
        {t.app.openDocumentation}
      </a>,
    );
    return () => {
      setEnd(null);
    };
  }, [setEnd, t]);

  return (
    <div
      className={cn(
        "flex min-h-0 w-full min-w-0 flex-1 flex-col",
        "p-1 sm:p-4 lg:p-6",
      )}
    >
      <PluginSlot name="docs:top" />
      <Card
        className={cn(
          "min-h-0 w-full min-w-0 flex-1 overflow-hidden flex flex-col",
          "border-border/40 shadow-2xl",
        )}
      >
        <iframe
          title={t.app.nav.documentation}
          src={HERMES_DOCS_URL}
          className={cn(
            "min-h-0 w-full min-w-0 flex-1",
            // Docusaurus paints over a transparent <html> / <body> and
            // relies on the browser's canvas color (light by default) to
            // fill the viewport. Inheriting the dashboard's dark color
            // scheme makes that canvas dark, so the docs body text — which
            // is tuned for a light canvas — becomes near-invisible. Force a
            // light color scheme + white background on the iframe element so
            // the docs render cleanly regardless of the active dashboard
            // theme or the user's prefers-color-scheme.
            "[color-scheme:light] bg-white",
          )}
          sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
          referrerPolicy="no-referrer-when-downgrade"
        />
      </Card>
      <PluginSlot name="docs:bottom" />
    </div>
  );
}
