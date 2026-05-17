import { useLayoutEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRight, CheckCircle2, GitCompare, Share2, Terminal, Wrench, XCircle } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent } from "@/components/ui/card";
import { usePageHeader } from "@/contexts/usePageHeader";

function LiveReplayArtifact() {
  const timeline = [
    { label: "Prompt", detail: "Build SaaS onboarding flow", status: "ok" },
    { label: "Tool", detail: "terminal: npm install", status: "ok" },
    { label: "File change", detail: "src/pages/Billing.tsx", status: "ok" },
    { label: "Failure", detail: "npm build → missing API_BASE_URL", status: "fail" },
  ];

  return (
    <div className="relative mx-auto max-w-4xl border border-border bg-background shadow-2xl shadow-primary/10">
      <div className="flex items-center justify-between border-b border-border bg-secondary/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-destructive" />
          <span className="h-2.5 w-2.5 rounded-full bg-warning" />
          <span className="h-2.5 w-2.5 rounded-full bg-success" />
        </div>
        <Badge tone="warning" className="text-[10px]">LIVE REPLAY</Badge>
      </div>

      <div className="grid gap-0 lg:grid-cols-[220px_minmax(0,1fr)_240px]">
        <aside className="border-b border-border p-4 lg:border-b-0 lg:border-r">
          <p className="mb-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">Timeline</p>
          <div className="space-y-3">
            {timeline.map((item) => (
              <div key={item.label} className="flex gap-3">
                <div className={`mt-1 h-2.5 w-2.5 rounded-full ${item.status === "fail" ? "bg-destructive" : "bg-success"}`} />
                <div className="min-w-0">
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="truncate text-xs text-muted-foreground">{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <main className="p-5">
          <div className="mb-4 border border-warning/30 bg-warning/5 p-4">
            <div className="mb-3 flex items-center gap-2">
              <XCircle className="h-4 w-4 text-warning" />
              <p className="font-medium">Incident summary</p>
            </div>
            <div className="grid gap-3 text-sm sm:grid-cols-2">
              <div><span className="text-muted-foreground">Outcome:</span> failed</div>
              <div><span className="text-muted-foreground">Failure point:</span> npm build</div>
              <div><span className="text-muted-foreground">Last successful step:</span> dependency install</div>
              <div><span className="text-muted-foreground">Next step:</span> set API_BASE_URL</div>
            </div>
          </div>
          <div className="space-y-2">
            <pre className="overflow-hidden border border-border bg-black/40 p-3 font-mono-ui text-xs text-success">✓ Dependencies installed\n✓ Generated route files\n✗ Build failed: env var API_BASE_URL is required</pre>
            <div className="grid gap-2 sm:grid-cols-3">
              <Badge tone="outline">Messages</Badge>
              <Badge tone="outline">Tool calls</Badge>
              <Badge tone="outline">File changes</Badge>
            </div>
          </div>
        </main>

        <aside className="border-t border-border p-4 lg:border-l lg:border-t-0">
          <p className="mb-3 text-xs uppercase tracking-[0.16em] text-muted-foreground">Debug metadata</p>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Model</span><span>gpt-5.5</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Duration</span><span>4m 12s</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Tools</span><span>18</span></div>
            <div className="flex justify-between gap-2"><span className="text-muted-foreground">Tokens</span><span>42k</span></div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();
  const { setAfterTitle, setEnd } = usePageHeader();

  useLayoutEffect(() => {
    setAfterTitle(<Badge tone="secondary" className="text-xs">Replay product</Badge>);
    setEnd(null);
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [setAfterTitle, setEnd]);

  return (
    <div className="flex flex-col gap-10 py-4">
      <section className="mx-auto max-w-5xl text-center">
        <Badge tone="outline" className="mb-4">Hermes Replay Dashboard</Badge>
        <h1 className="font-mondwest text-4xl tracking-[0.12em] text-foreground md:text-6xl">
          Understand agent runs without reading raw logs first.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-muted-foreground md:text-lg">
          Manage every session, open replay investigations, share outcomes, and compare failed runs against successful ones.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button size="default" onClick={() => navigate("/sessions")}>
            Open dashboard
            <ArrowRight className="h-4 w-4" />
          </Button>
          <Button outlined size="default" onClick={() => navigate("/compare")}>
            <GitCompare className="h-4 w-4" />
            Compare replays
          </Button>
        </div>
      </section>

      <LiveReplayArtifact />

      <section className="grid gap-4 md:grid-cols-4">
        {[
          { icon: Activity, title: "Dashboard", body: "KPI cards and an action-first recent sessions table." },
          { icon: Terminal, title: "Replay", body: "Incident summary first; terminal output and logs only on drill-down." },
          { icon: Wrench, title: "Tools", body: "Tool calls, file changes, prompts, and checkpoints in one workspace." },
          { icon: Share2, title: "Share", body: "Copy replay links or export JSON for handoff and debugging." },
        ].map((item) => (
          <Card key={item.title}>
            <CardContent className="p-4">
              <item.icon className="mb-3 h-5 w-5 text-primary" />
              <p className="font-medium">{item.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{item.body}</p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="border border-border bg-secondary/20 p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="font-medium">Built for debugging action, not dumping data.</p>
            <p className="text-sm text-muted-foreground">
              Landing sells the product, dashboard manages sessions, replay investigates, compare powers advanced workflows.
            </p>
          </div>
          <div className="flex items-center gap-2 text-success">
            <CheckCircle2 className="h-4 w-4" />
            <span className="text-sm">Action-oriented UX</span>
          </div>
        </div>
      </section>
    </div>
  );
}
