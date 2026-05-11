(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;
  const React = SDK.React;
  const h = React.createElement;
  const C = SDK.components || {};
  const hooks = SDK.hooks || React;
  const useEffect = hooks.useEffect;
  const useMemo = hooks.useMemo;
  const useState = hooks.useState;

  const SECTION_ORDER = ["Active", "Waiting/Blocked", "Paused", "Ideas", "Archived / Parking Lot", "Standing Lanes"];
  const STATUS_CLASS = {
    active: "pi-status-active",
    waiting: "pi-status-waiting",
    blocked: "pi-status-waiting",
    paused: "pi-status-paused",
    idea: "pi-status-idea",
    parking: "pi-status-archive",
    archived: "pi-status-archive"
  };

  function apiFetch(path, options) {
    const token = window.__HERMES_SESSION_TOKEN__ || "";
    const headers = Object.assign({}, (options && options.headers) || {});
    if (token) headers["X-Hermes-Session-Token"] = token;
    return fetch("/api/plugins/projects-ideas" + path, Object.assign({ credentials: "same-origin", headers: headers }, options || {}))
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      });
  }

  function CardShell(props) {
    if (C.Card && C.CardContent) {
      return h(C.Card, { className: props.className }, h(C.CardContent, { className: "pi-card-content" }, props.children));
    }
    return h("div", { className: "pi-card " + (props.className || "") }, props.children);
  }

  function Pill(props) {
    if (C.Badge) return h(C.Badge, { className: props.className }, props.children);
    return h("span", { className: "pi-pill " + (props.className || "") }, props.children);
  }

  function ProjectCard(props) {
    const card = props.card;
    const links = card.links || [];
    return h(CardShell, { className: "pi-card " + (STATUS_CLASS[card.status] || "") },
      h("div", { className: "pi-card-top" },
        h("div", null,
          h("div", { className: "pi-card-kicker" }, (card.kind || "card").replace("_", " ")),
          h("h3", null, card.name)
        ),
        h(Pill, { className: "pi-priority pi-priority-" + card.priority }, card.priority || "normal")
      ),
      h("p", { className: "pi-summary" }, card.summary),
      h("dl", { className: "pi-meta" },
        h("div", null, h("dt", null, "Owner"), h("dd", null, card.owner || "—")),
        h("div", null, h("dt", null, "Last activity"), h("dd", null, card.last_activity || "—")),
        card.stage ? h("div", null, h("dt", null, "Stage"), h("dd", null, card.stage)) : null,
        card.potential_value ? h("div", null, h("dt", null, "Potential"), h("dd", null, card.potential_value)) : null
      ),
      h("div", { className: "pi-next" }, h("strong", null, "Next meaningful action: "), card.next_action),
      card.evidence ? h("p", { className: "pi-evidence" }, h("strong", null, "Evidence: "), card.evidence) : null,
      card.signals && card.signals.length ? h("div", { className: "pi-signals" }, card.signals.slice(0, 5).map(function (s) { return h("span", { key: s }, s); })) : null,
      links.length ? h("div", { className: "pi-links" }, links.map(function (link) {
        return h("a", { key: link.label + link.url, href: link.url, target: link.url && link.url[0] === "/" ? undefined : "_blank", rel: "noreferrer" }, link.label);
      })) : null
    );
  }

  function ProjectsIdeasPage() {
    const [data, setData] = useState(null);
    const [filter, setFilter] = useState("all");
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    function load(refresh) {
      setLoading(true); setError(null);
      apiFetch(refresh ? "/refresh" : "/snapshot", refresh ? { method: "POST" } : undefined)
        .then(function (json) { setData(json); })
        .catch(function (err) { setError(err.message || String(err)); })
        .finally(function () { setLoading(false); });
    }
    useEffect(function () { load(false); }, []);

    const cardsBySection = useMemo(function () {
      const out = {};
      SECTION_ORDER.forEach(function (s) { out[s] = []; });
      ((data && data.cards) || []).forEach(function (card) {
        if (filter !== "all" && card.kind !== filter && card.status !== filter) return;
        const lane = card.lane || "Ideas";
        (out[lane] || (out[lane] = [])).push(card);
      });
      return out;
    }, [data, filter]);

    if (loading && !data) return h("div", { className: "pi-page" }, h("div", { className: "pi-loading" }, "Loading Ryan's project portfolio…"));
    if (error && !data) return h("div", { className: "pi-page" }, h("div", { className: "pi-error" }, "Could not load Projects + Ideas: " + error));

    return h("div", { className: "pi-page" },
      h("header", { className: "pi-hero" },
        h("div", null,
          h("p", { className: "pi-eyebrow" }, "Private command-center"),
          h("h1", null, data.title || "Ryan Projects + Ideas"),
          h("p", null, data.subtitle)
        ),
        h("div", { className: "pi-actions" },
          h("button", { className: "pi-button", onClick: function () { load(true); }, disabled: loading }, loading ? "Refreshing…" : "Refresh from sources"),
          h("span", { className: "pi-generated" }, data.generated_at ? "Updated " + new Date(data.generated_at * 1000).toLocaleString() : "")
        )
      ),
      h("section", { className: "pi-review-note" },
        h("strong", null, "What Ryan should notice: "),
        "this is not another Linear board. Active work, standing workflows, raw ideas, and archived/parking-lot items live in separate scan lanes, each with one next meaningful action."
      ),
      h("section", { className: "pi-stats" }, SECTION_ORDER.map(function (section) {
        return h("button", { key: section, className: "pi-stat", onClick: function () { setFilter("all"); } },
          h("span", null, section), h("strong", null, ((data.counts || {})[section] || 0))
        );
      })),
      h("div", { className: "pi-filters" }, ["all", "project", "standing_lane", "idea", "waiting", "paused", "parking"].map(function (v) {
        return h("button", { key: v, className: filter === v ? "active" : "", onClick: function () { setFilter(v); } }, v.replace("_", " "));
      })),
      error ? h("div", { className: "pi-warning" }, "Last refresh failed: " + error) : null,
      h("main", { className: "pi-sections" }, SECTION_ORDER.map(function (section) {
        const cards = cardsBySection[section] || [];
        return h("section", { className: "pi-section", key: section },
          h("div", { className: "pi-section-head" }, h("h2", null, section), h("span", null, cards.length + " cards")),
          cards.length ? h("div", { className: "pi-grid" }, cards.map(function (card) { return h(ProjectCard, { key: card.id, card: card }); })) :
            h("div", { className: "pi-empty" }, "No cards in this lane yet.")
        );
      })),
      h("footer", { className: "pi-footer" },
        h("p", null, data.privacy_note),
        h("p", null, data.refresh_path)
      )
    );
  }

  window.__HERMES_PLUGINS__.register("projects-ideas", ProjectsIdeasPage);
})();
