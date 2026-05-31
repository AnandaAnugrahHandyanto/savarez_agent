(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  const React = SDK.React;
  const h = React.createElement;
  const C = SDK.components;
  const cards = [["Follow-ups", "Use Kanban cards for person-specific next actions until the people-note backend is wired."], ["Source of truth", "Curated people context belongs in Rolly brain wiki notes; raw conversations stay in session history."], ["Human gate", "Outreach and contact changes stay human-approved by default."]];
  const visibilityLinks = [["Kanban", "/kanban"], ["Sessions", "/sessions"], ["Logs", "/logs"], ["Cron", "/cron"], ["Chat", "/chat"]];

  function navigate(path) {
    const base = (window.__HERMES_BASE_PATH__ || "").replace(/\/+$/, "");
    window.history.pushState(null, "", base + path);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }

  function LinkButton(props) {
    return h(C.Button || "button", {
      onClick: function () { navigate(props.href); },
      className: props.className || "",
    }, props.children);
  }

  function SectionCard(props) {
    return h(C.Card || "div", { className: "border border-current/15 bg-background-base/70" },
      h(C.CardContent || "div", { className: "p-4" },
        h("div", { className: "font-mondwest text-display text-sm uppercase tracking-[0.12em] text-midground" }, props.title),
        h("p", { className: "mt-2 text-sm leading-6 text-text-secondary" }, props.body)
      )
    );
  }

  function RollyOpsPage() {
    return h("main", { className: "mx-auto flex w-full max-w-6xl flex-col gap-5 pb-8" },
      h("section", { className: "rounded border border-current/15 bg-background-base/70 p-5" },
        h("div", { className: "text-xs uppercase tracking-[0.22em] text-text-tertiary" }, "Rolly ops"),
        h("h1", { className: "mt-2 font-mondwest text-display text-3xl uppercase tracking-[0.08em] text-midground" }, "People"),
        h("p", { className: "mt-3 max-w-3xl text-sm leading-6 text-text-secondary" }, "Relationship surface for leads, collaborators, and family onboarding."),
        h("div", { className: "mt-4 flex flex-wrap gap-2" },
          h(LinkButton, { href: "/kanban", className: "text-xs" }, "Open People Kanban"),
          h(LinkButton, { href: "/kanban", className: "text-xs" }, "Open Kanban")
        )
      ),
      h("section", { className: "grid gap-3 md:grid-cols-3" },
        cards.map(function (card) { return h(SectionCard, { key: card[0], title: card[0], body: card[1] }); })
      ),
      h("section", { className: "grid gap-3 lg:grid-cols-2" },
        h(SectionCard, { title: "Activity", body: "Use this tab as an operations landing page. Current activity still comes from Kanban task events, Sessions, Cron, and Logs." }),
        h(C.Card || "div", { className: "border border-current/15 bg-background-base/70" },
          h(C.CardContent || "div", { className: "p-4" },
            h("div", { className: "font-mondwest text-display text-sm uppercase tracking-[0.12em] text-midground" }, "Visibility"),
            h("div", { className: "mt-3 flex flex-wrap gap-2" },
              visibilityLinks.map(function (link) {
                return h(LinkButton, { key: link[0], href: link[1], className: "text-xs" }, link[0]);
              })
            )
          )
        )
      )
    );
  }

  window.__HERMES_PLUGINS__.register("rolly-people", RollyOpsPage);
})();
