# nix/python.nix — uv2nix virtual environment builder
{
  python311,
  lib,
  callPackage,
  uv2nix,
  pyproject-nix,
  pyproject-build-systems,
}:
let
  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./..; };

  overlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel";
  };

  pythonSet =
    (callPackage pyproject-nix.build.packages {
      python = python311;
    }).overrideScope
      (lib.composeManyExtensions [
        pyproject-build-systems.overlays.default
        overlay
      ]);
  # onnxruntime (pulled in by the "voice" extra) does not publish aarch64-darwin
  # wheels, causing nix profile install to fail on Apple Silicon.
  # Exclude the voice extra on macOS aarch64; all other extras remain available.
  hermesExtras =
    if (lib.systems.elaborate { system = builtins.currentSystem; }).isAarch64 &&
       (lib.systems.elaborate { system = builtins.currentSystem; }).isDarwin
    then
      builtins.filter (e: e != "voice") (lib.attrNames (lib.importTOML ../pyproject.toml).project.optional-dependencies)
    else
      [ "all" ];
in
pythonSet.mkVirtualEnv "hermes-agent-env" {
  hermes-agent = hermesExtras;
}
