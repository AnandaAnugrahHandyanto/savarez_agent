type ObservabilityConfig = {
  enabled: boolean;
  posthog_host: string;
  posthog_project_api_key: string;
  env: string;
  service: string;
  version: string;
};

type Properties = Record<string, unknown>;

let initialized = false;
let initStarted: Promise<void> | null = null;
let enabled = false;
let posthogClient: { capture: (event: string, properties?: Properties) => void } | null = null;
let lastTraceId = "";
let lastRequestId = "";
let publicConfig: ObservabilityConfig | null = null;

function readBasePath(): string {
  if (typeof window === "undefined") return "";
  const raw = window.__HERMES_BASE_PATH__ ?? "";
  if (!raw) return "";
  const withLead = raw.startsWith("/") ? raw : `/${raw}`;
  return withLead.replace(/\/+$/, "");
}

async function loadConfig(): Promise<ObservabilityConfig | null> {
  if (publicConfig) return publicConfig;
  try {
    const res = await fetch(`${readBasePath()}/api/observability/config`);
    if (!res.ok) return null;
    publicConfig = (await res.json()) as ObservabilityConfig;
    return publicConfig;
  } catch {
    return null;
  }
}

async function init(): Promise<void> {
  if (initialized) return;
  if (initStarted) return initStarted;
  initStarted = (async () => {
    const cfg = await loadConfig();
    if (!cfg?.enabled || !cfg.posthog_project_api_key) {
      initialized = true;
      enabled = false;
      return;
    }
    try {
      const mod = await import("posthog-js");
      const posthog = mod.default;
      posthog.init(cfg.posthog_project_api_key, {
        api_host: cfg.posthog_host,
        autocapture: false,
        capture_pageview: false,
        persistence: "localStorage+cookie",
      });
      posthogClient = posthog;
      enabled = true;
    } catch {
      enabled = false;
    } finally {
      initialized = true;
    }
  })();
  return initStarted;
}

function baseProperties(properties?: Properties): Properties {
  return {
    ...(properties ?? {}),
    trace_id: properties?.trace_id ?? lastTraceId,
    request_id: properties?.request_id ?? lastRequestId,
    env: publicConfig?.env,
    service: publicConfig?.service,
    version: publicConfig?.version,
    source: "dashboard",
  };
}

export const analytics = {
  async init(): Promise<void> {
    await init();
  },

  rememberResponse(response: Response): void {
    lastTraceId = response.headers.get("X-Trace-Id") || lastTraceId;
    lastRequestId = response.headers.get("X-Request-Id") || lastRequestId;
  },

  track(eventName: string, properties?: Properties): void {
    void init().then(() => {
      if (!enabled || !posthogClient) return;
      posthogClient.capture(eventName, baseProperties(properties));
    });
  },

  context(): { trace_id: string; request_id: string } {
    return { trace_id: lastTraceId, request_id: lastRequestId };
  },
};
