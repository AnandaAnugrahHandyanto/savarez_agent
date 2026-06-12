// Clawley Cockpit dashboard plugin entry.
// Kept deliberately dependency-light: the host dashboard loads this bundle and
// can call window.ClawleyCockpit.mount(root, { apiBase }) when rendering the tab.
(function () {
  async function fetchStatus(apiBase) {
    const response = await fetch(`${apiBase || '/api/plugins/clawley-cockpit'}/status`, { credentials: 'include' });
    if (!response.ok) throw new Error(`status ${response.status}`);
    return response.json();
  }

  function render(root, payload) {
    const sections = payload.sections || {};
    root.innerHTML = `
      <section style="padding:16px;font-family:system-ui,sans-serif">
        <h1>Clawley Cockpit</h1>
        <p><strong>Read-only:</strong> ${payload.safety_flags && payload.safety_flags.read_only ? 'yes' : 'unknown'}</p>
        <pre style="white-space:pre-wrap;background:#111;color:#eee;padding:12px;border-radius:8px">${escapeHtml(JSON.stringify(sections, null, 2))}</pre>
      </section>`;
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  }

  window.ClawleyCockpit = {
    async mount(root, options) {
      root.textContent = 'Loading Clawley cockpit…';
      try {
        render(root, await fetchStatus(options && options.apiBase));
      } catch (error) {
        root.textContent = `Clawley cockpit unavailable: ${error.message}`;
      }
    },
  };
})();
