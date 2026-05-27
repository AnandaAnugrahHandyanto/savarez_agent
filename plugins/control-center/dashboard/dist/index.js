(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK) return;
  const React = SDK.React;
  const h = React.createElement;
  const hooks = SDK.hooks || React;
  const useEffect = hooks.useEffect, useMemo = hooks.useMemo, useState = hooks.useState;
  const C = SDK.components || {};
  const Button = C.Button || "button";
  const Card = C.Card || "div";
  const CardContent = C.CardContent || "div";
  const Input = C.Input || "input";
  const Badge = C.Badge || "span";

  function headers(extra) {
    const out = Object.assign({}, extra || {});
    const token = window.__HERMES_SESSION_TOKEN__ || "";
    if (token) out["X-Hermes-Session-Token"] = token;
    return out;
  }
  async function json(url, opts) {
    const res = await fetch(url, Object.assign({}, opts || {}, { headers: headers((opts && opts.headers) || {}) }));
    if (!res.ok) throw new Error(res.status + ": " + await res.text());
    return res.json();
  }
  const cc = (p, opts) => json("/api/plugins/control-center" + p, opts);
  const kb = (p, opts) => json("/api/plugins/kanban" + p, opts);

  function TabButton(props) {
    return h("button", { className: "hc-tab" + (props.active ? " hc-tab-active" : ""), onClick: props.onClick }, props.children);
  }
  function ErrorBox({ error }) {
    return error ? h("div", { className: "hc-error" }, String(error.message || error)) : null;
  }
  function Stat({ label, value }) {
    return h("div", { className: "hc-stat" }, h("div", { className: "hc-stat-value" }, value), h("div", { className: "hc-stat-label" }, label));
  }

  function KanbanTab() {
    const [board, setBoard] = useState(null);
    const [error, setError] = useState(null);
    const [title, setTitle] = useState("");
    const [body, setBody] = useState("");
    const [tenant, setTenant] = useState("projects");
    const [busy, setBusy] = useState(false);
    const columns = board && board.columns ? board.columns : [];
    const totals = useMemo(function () {
      const t = { total: 0, running: 0, blocked: 0, done: 0 };
      columns.forEach(function (c) { const n = (c.tasks || []).length; t.total += n; if (c.name in t) t[c.name] = n; });
      return t;
    }, [board]);
    function load() {
      setError(null);
      kb("/board?tenant=" + encodeURIComponent(tenant || "projects"))
        .then(setBoard).catch(setError);
    }
    useEffect(load, [tenant]);
    async function createTask(e) {
      e && e.preventDefault && e.preventDefault();
      if (!title.trim()) return;
      setBusy(true); setError(null);
      try {
        await kb("/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim(), body: body.trim() || null, tenant: tenant || "projects", triage: true }) });
        setTitle(""); setBody(""); load();
      } catch (err) { setError(err); }
      finally { setBusy(false); }
    }
    async function move(task, status) {
      setError(null);
      try { await kb("/tasks/" + encodeURIComponent(task.id), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: status }) }); load(); }
      catch (err) { setError(err); }
    }
    return h("div", { className: "hc-grid" },
      h("section", { className: "hc-main" },
        h("div", { className: "hc-toolbar" },
          h("div", null, h("h2", null, "Project Kanban"), h("p", null, "Backed by the existing Hermes Kanban board.")),
          h("div", { className: "hc-tenant" }, h("label", null, "Tenant"), h(Input, { value: tenant, onChange: e => setTenant(e.target.value), placeholder: "projects" }), h(Button, { onClick: load }, "Refresh"))
        ),
        h(ErrorBox, { error }),
        h("div", { className: "hc-stats" }, h(Stat, { label: "Tasks", value: totals.total }), h(Stat, { label: "Running", value: totals.running }), h(Stat, { label: "Blocked", value: totals.blocked }), h(Stat, { label: "Done", value: totals.done })),
        h("div", { className: "hc-board" }, columns.map(function (col) {
          return h("div", { className: "hc-col", key: col.name },
            h("div", { className: "hc-col-head" }, h("span", null, col.name), h("span", null, (col.tasks || []).length)),
            (col.tasks || []).length ? (col.tasks || []).map(function (task) {
              return h("div", { className: "hc-card", key: task.id },
                h("div", { className: "hc-card-title" }, task.title),
                task.assignee ? h("div", { className: "hc-muted" }, "@" + task.assignee) : null,
                task.latest_summary ? h("p", { className: "hc-muted" }, task.latest_summary) : null,
                h("div", { className: "hc-actions" }, ["triage", "todo", "ready", "blocked", "done"].filter(s => s !== col.name).map(s => h("button", { key: s, onClick: () => move(task, s) }, s)))
              );
            }) : h("div", { className: "hc-empty" }, "No cards")
          );
        }))
      ),
      h("aside", { className: "hc-side" },
        h("h3", null, "New project card"),
        h("form", { onSubmit: createTask },
          h("label", null, "Title"), h(Input, { value: title, onChange: e => setTitle(e.target.value), placeholder: "Build X" }),
          h("label", null, "Body"), h("textarea", { value: body, onChange: e => setBody(e.target.value), rows: 8, placeholder: "Acceptance criteria, context, links…" }),
          h(Button, { disabled: busy || !title.trim(), type: "submit" }, busy ? "Creating…" : "Create triage card")
        )
      )
    );
  }

  function WikisTab() {
    const [wikis, setWikis] = useState([]);
    const [selected, setSelected] = useState("");
    const [pages, setPages] = useState([]);
    const [q, setQ] = useState("");
    const [activeFile, setActiveFile] = useState("index.md");
    const [content, setContent] = useState("");
    const [lint, setLint] = useState(null);
    const [error, setError] = useState(null);
    const [newPath, setNewPath] = useState("");
    const [domain, setDomain] = useState("General research knowledge base");
    const activeWiki = wikis.find(w => w.path === selected) || wikis[0];
    function loadWikis() { setError(null); cc("/wikis").then(d => { setWikis(d.wikis || []); if (!selected && (d.wikis || [])[0]) setSelected(d.wikis[0].path); }).catch(setError); }
    function loadPages() { if (!activeWiki) return; cc("/wiki/pages?path=" + encodeURIComponent(activeWiki.path) + "&q=" + encodeURIComponent(q)).then(d => setPages(d.pages || [])).catch(setError); }
    function read(file) { if (!activeWiki || !file) return; setActiveFile(file); cc("/wiki/page?path=" + encodeURIComponent(activeWiki.path) + "&file=" + encodeURIComponent(file)).then(d => setContent(d.content || "")).catch(setError); }
    useEffect(loadWikis, []);
    useEffect(loadPages, [selected, q]);
    useEffect(function () { if (activeWiki && activeWiki.initialized) read(activeFile || "index.md"); }, [selected]);
    async function initWiki() {
      setError(null);
      try { const d = await cc("/wikis/init", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: newPath || null, domain }) }); setSelected(d.wiki.path); loadWikis(); }
      catch (err) { setError(err); }
    }
    async function savePage() {
      setError(null);
      try { await cc("/wiki/page?path=" + encodeURIComponent(activeWiki.path), { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path: activeFile, content }) }); loadPages(); }
      catch (err) { setError(err); }
    }
    async function runLint() { setError(null); try { setLint(await cc("/wiki/lint?path=" + encodeURIComponent(activeWiki.path))); } catch (err) { setError(err); } }
    return h("div", { className: "hc-grid" },
      h("section", { className: "hc-main" },
        h("div", { className: "hc-toolbar" }, h("div", null, h("h2", null, "LLM Wikis"), h("p", null, "Initialize, browse, edit, and lint Karpathy-style markdown wikis.")), activeWiki ? h(Badge, null, activeWiki.page_count + " pages") : null),
        h(ErrorBox, { error }),
        h("div", { className: "hc-toolbar" },
          h("select", { value: selected, onChange: e => setSelected(e.target.value) }, wikis.map(w => h("option", { key: w.path, value: w.path }, (w.initialized ? "✓ " : "○ ") + w.name + " — " + w.path))),
          h(Input, { value: q, onChange: e => setQ(e.target.value), placeholder: "Search pages" }),
          h(Button, { onClick: loadWikis }, "Refresh"), h(Button, { onClick: runLint, disabled: !activeWiki || !activeWiki.initialized }, "Lint")
        ),
        activeWiki && !activeWiki.initialized ? h("div", { className: "hc-callout" }, "This path is not initialized as an LLM wiki yet. Use the initializer on the right.") : null,
        lint ? h("div", { className: "hc-lint" }, h("strong", null, "Lint: "), Object.keys(lint.counts || {}).map(k => h("span", { key: k }, k + ": " + lint.counts[k] + " "))) : null,
        h("div", { className: "hc-wiki-layout" },
          h("div", { className: "hc-pages" }, ["SCHEMA.md", "index.md", "log.md"].map(f => h("button", { key: f, onClick: () => read(f), className: activeFile === f ? "active" : "" }, f)).concat(pages.map(p => h("button", { key: p.path, onClick: () => read(p.path), className: activeFile === p.path ? "active" : "" }, p.path)))),
          h("div", { className: "hc-editor" }, h("div", { className: "hc-editor-head" }, h("strong", null, activeFile), h(Button, { onClick: savePage, disabled: !activeWiki || !activeWiki.initialized }, "Save")), h("textarea", { value: content, onChange: e => setContent(e.target.value), rows: 28 }))
        )
      ),
      h("aside", { className: "hc-side" },
        h("h3", null, "Initialize wiki"),
        h("label", null, "Path"), h(Input, { value: newPath, onChange: e => setNewPath(e.target.value), placeholder: "blank = WIKI_PATH or ~/wiki" }),
        h("label", null, "Domain"), h("textarea", { value: domain, onChange: e => setDomain(e.target.value), rows: 5 }),
        h(Button, { onClick: initWiki }, "Initialize / register")
      )
    );
  }

  function PromptsTab() {
    const empty = { command: "/", name: "", content: "", tags: "" };
    const [prompts, setPrompts] = useState([]);
    const [selected, setSelected] = useState(null);
    const [form, setForm] = useState(empty);
    const [q, setQ] = useState("");
    const [owui, setOwui] = useState(null);
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    function tagsArray(value) { return String(value || "").split(",").map(t => t.trim()).filter(Boolean); }
    function edit(prompt) {
      setSelected(prompt || null);
      setForm(prompt ? { command: prompt.command || "/", name: prompt.name || "", content: prompt.content || "", tags: (prompt.tags || []).join(", ") } : empty);
    }
    function load() {
      setError(null);
      cc("/prompts?q=" + encodeURIComponent(q)).then(d => { setPrompts(d.prompts || []); if (!selected && (d.prompts || [])[0]) edit(d.prompts[0]); }).catch(setError);
    }
    function loadOpenWebUI() { setError(null); cc("/prompts/open-webui").then(setOwui).catch(setError); }
    useEffect(load, [q]);
    useEffect(loadOpenWebUI, []);
    async function savePrompt(e) {
      e && e.preventDefault && e.preventDefault();
      setBusy(true); setError(null);
      const payload = { command: form.command, name: form.name, content: form.content, tags: tagsArray(form.tags) };
      try {
        const path = selected ? "/prompts/" + encodeURIComponent(selected.id) : "/prompts";
        const method = selected ? "PUT" : "POST";
        const d = await cc(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        edit(d.prompt); load();
      } catch (err) { setError(err); }
      finally { setBusy(false); }
    }
    async function deletePrompt() {
      if (!selected) return;
      setBusy(true); setError(null);
      try { await cc("/prompts/" + encodeURIComponent(selected.id), { method: "DELETE" }); edit(null); load(); }
      catch (err) { setError(err); }
      finally { setBusy(false); }
    }
    async function importOpenWebUI() {
      setBusy(true); setError(null);
      try { await cc("/prompts/import-open-webui", { method: "POST" }); await loadOpenWebUI(); load(); }
      catch (err) { setError(err); }
      finally { setBusy(false); }
    }
    return h("div", { className: "hc-grid" },
      h("section", { className: "hc-main" },
        h("div", { className: "hc-toolbar" }, h("div", null, h("h2", null, "Prompt Library"), h("p", null, "Create, search, edit, delete, and import Open WebUI prompt shortcuts.")), h(Badge, null, prompts.length + " prompts")),
        h(ErrorBox, { error }),
        h("div", { className: "hc-toolbar" }, h(Input, { value: q, onChange: e => setQ(e.target.value), placeholder: "Search command, name, content" }), h(Button, { onClick: () => edit(null) }, "New"), h(Button, { onClick: load }, "Refresh")),
        h("div", { className: "hc-wiki-layout" },
          h("div", { className: "hc-pages" }, prompts.length ? prompts.map(p => h("button", { key: p.id, className: selected && selected.id === p.id ? "active" : "", onClick: () => edit(p) }, (p.command || "") + " — " + (p.name || "Untitled"))) : h("div", { className: "hc-empty" }, "No prompts yet")),
          h("form", { className: "hc-editor", onSubmit: savePrompt },
            h("div", { className: "hc-editor-head" }, h("strong", null, selected ? "Edit prompt" : "New prompt"), h("div", { className: "hc-actions" }, h(Button, { disabled: busy || !form.command || !form.name, type: "submit" }, busy ? "Saving…" : "Save"), selected ? h("button", { type: "button", onClick: deletePrompt }, "Delete") : null)),
            h("label", null, "Command"), h(Input, { value: form.command, onChange: e => setForm(Object.assign({}, form, { command: e.target.value })), placeholder: "/brief" }),
            h("label", null, "Name"), h(Input, { value: form.name, onChange: e => setForm(Object.assign({}, form, { name: e.target.value })), placeholder: "Briefing prompt" }),
            h("label", null, "Tags"), h(Input, { value: form.tags, onChange: e => setForm(Object.assign({}, form, { tags: e.target.value })), placeholder: "research, briefing" }),
            h("label", null, "Content"), h("textarea", { value: form.content, onChange: e => setForm(Object.assign({}, form, { content: e.target.value })), rows: 24, placeholder: "Prompt text. Use {{variables}} if useful." })
          )
        )
      ),
      h("aside", { className: "hc-side" },
        h("h3", null, "Open WebUI import"),
        h("p", { className: "hc-muted" }, owui ? (owui.total + " prompt(s) found in " + owui.db) : "Checking Open WebUI prompt database…"),
        owui && owui.prompts && owui.prompts.length ? h("div", { className: "hc-pages" }, owui.prompts.slice(0, 10).map(p => h("button", { key: p.id, type: "button" }, (p.command || "") + " — " + (p.name || "Untitled")))) : h("div", { className: "hc-empty" }, "No Open WebUI prompts found"),
        h(Button, { onClick: importOpenWebUI, disabled: busy || !owui || !owui.total }, "Import / sync Open WebUI prompts")
      )
    );
  }

  function ControlCenter() {
    const [tab, setTab] = useState("kanban");
    return h("div", { className: "hermes-control-center" },
      h("div", { className: "hc-header" }, h("div", null, h("h1", null, "Hermes Control Center"), h("p", null, "Operations cockpit for project work, prompts, and compounding research wikis.")), h("div", { className: "hc-tabs" }, h(TabButton, { active: tab === "kanban", onClick: () => setTab("kanban") }, "Projects Kanban"), h(TabButton, { active: tab === "prompts", onClick: () => setTab("prompts") }, "Prompt Library"), h(TabButton, { active: tab === "wikis", onClick: () => setTab("wikis") }, "LLM Wikis"))),
      tab === "kanban" ? h(KanbanTab) : (tab === "prompts" ? h(PromptsTab) : h(WikisTab))
    );
  }

  if (window.__HERMES_PLUGINS__ && window.__HERMES_PLUGINS__.register) {
    window.__HERMES_PLUGINS__.register("control-center", ControlCenter);
  }
})();
