(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;

  const React = SDK.React;
  const h = React.createElement;
  const C = SDK.components || {};
  const hooks = SDK.hooks || React;
  const Card = C.Card || "div";
  const CardContent = C.CardContent || "div";
  const Button = C.Button || "button";
  const Badge = C.Badge || "span";
  const useState = hooks.useState || React.useState;
  const useEffect = hooks.useEffect || React.useEffect;

  const API_BASE = "/api/plugins/artifacts";

  function api(path) {
    return fetch(API_BASE + path).then(function (res) {
      if (!res.ok) {
        return res.text().then(function (text) {
          throw new Error(res.status + ": " + (text || res.statusText));
        });
      }
      return res.json();
    });
  }

  function ArtifactCard(props) {
    const artifact = props.artifact;
    const selected = props.selected && props.selected.id === artifact.id;
    return h(Card, {
      className: "hermes-artifact-card" + (selected ? " hermes-artifact-card-selected" : ""),
      onClick: function () { props.onSelect(artifact); },
      role: "button",
      tabIndex: 0,
      onKeyDown: function (event) {
        if (event.key === "Enter" || event.key === " ") props.onSelect(artifact);
      }
    },
      h(CardContent, { className: "hermes-artifact-card-content" },
        h("div", { className: "hermes-artifact-card-title" }, artifact.title || artifact.id),
        h("div", { className: "hermes-artifact-card-meta" },
          h(Badge, null, artifact.contentType || "unknown"),
          h("span", null, "v" + (artifact.latestVersion || 1))
        ),
        artifact.description ? h("p", { className: "hermes-artifact-card-description" }, artifact.description) : null
      )
    );
  }

  function EmptyState() {
    return h("div", { className: "hermes-artifacts-empty" },
      h("h3", null, "No artifacts yet"),
      h("p", null, "Artifacts will appear here once a builder or tool registers manifests under HERMES_HOME/artifacts.")
    );
  }

  function Preview(props) {
    const artifact = props.artifact;
    if (!artifact) {
      return h("section", { className: "hermes-artifact-preview hermes-artifact-preview-empty" },
        h("h3", null, "Select an artifact"),
        h("p", null, "Preview runs in a sandboxed iframe. No same-origin bridge. No tiny browser demon gets dashboard cookies.")
      );
    }
    return h("section", { className: "hermes-artifact-preview" },
      h("div", { className: "hermes-artifact-preview-header" },
        h("div", null,
          h("h2", null, artifact.title || artifact.id),
          h("p", null, artifact.id + " · " + (artifact.contentType || "unknown"))
        ),
        h(Button, {
          type: "button",
          onClick: function () { window.open(artifact.previewUrl, "_blank", "noopener,noreferrer"); }
        }, "Open raw")
      ),
      h("iframe", {
        title: "Artifact preview: " + (artifact.title || artifact.id),
        className: "hermes-artifact-iframe",
        sandbox: "allow-scripts",
        referrerPolicy: "no-referrer",
        src: artifact.previewUrl
      })
    );
  }

  function ArtifactsPage() {
    const _state = useState([]);
    const artifacts = _state[0];
    const setArtifacts = _state[1];
    const _selected = useState(null);
    const selected = _selected[0];
    const setSelected = _selected[1];
    const _loading = useState(true);
    const loading = _loading[0];
    const setLoading = _loading[1];
    const _error = useState(null);
    const error = _error[0];
    const setError = _error[1];

    function load() {
      setLoading(true);
      setError(null);
      return api("/list")
        .then(function (data) {
          const list = data.artifacts || [];
          setArtifacts(list);
          setSelected(function (current) {
            if (current && list.some(function (item) { return item.id === current.id; })) return current;
            return list[0] || null;
          });
        })
        .catch(function (err) { setError(err.message || String(err)); })
        .finally(function () { setLoading(false); });
    }

    useEffect(function () { load(); }, []);

    return h("div", { className: "hermes-artifacts-page" },
      h("header", { className: "hermes-artifacts-header" },
        h("div", null,
          h("h1", null, "Artifacts"),
          h("p", null, "Local immutable artifact previews rendered in a sandboxed iframe.")
        ),
        h(Button, { type: "button", onClick: load, disabled: loading }, loading ? "Loading…" : "Refresh")
      ),
      error ? h("div", { className: "hermes-artifacts-error" }, error) : null,
      h("main", { className: "hermes-artifacts-layout" },
        h("aside", { className: "hermes-artifacts-list" },
          loading ? h("p", { className: "hermes-artifacts-muted" }, "Loading artifacts…") : null,
          !loading && artifacts.length === 0 ? h(EmptyState) : null,
          artifacts.map(function (artifact) {
            return h(ArtifactCard, {
              key: artifact.id,
              artifact: artifact,
              selected: selected,
              onSelect: setSelected
            });
          })
        ),
        h(Preview, { artifact: selected })
      )
    );
  }

  SDK.registerPage({
    path: "/artifacts",
    name: "artifacts",
    label: "Artifacts",
    component: ArtifactsPage
  });
})();
