(function () {
  const sdk = window.__HERMES_PLUGIN_SDK__;
  const plugins = window.__HERMES_PLUGINS__;

  if (!sdk || !plugins) {
    return;
  }

  const React = sdk.React;

  function ExampleDashboardPlugin() {
    return React.createElement(
      "div",
      {
        style: {
          border: "1px solid rgba(255, 255, 255, 0.18)",
          padding: "1rem",
        },
      },
      React.createElement("h2", null, "Example dashboard plugin"),
      React.createElement(
        "p",
        null,
        "Bundled inert sample plugin used for dashboard plugin loading checks.",
      ),
    );
  }

  plugins.register("example", ExampleDashboardPlugin);
})();
