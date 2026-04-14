# nix/packages.nix — Hermes Agent package built with uv2nix
{ inputs, ... }: {
  perSystem = { pkgs, system, ... }:
    let
      hermesVenv = pkgs.callPackage ./python.nix {
        inherit (inputs) uv2nix pyproject-nix pyproject-build-systems;
      };

      # Import bundled skills, excluding runtime caches
      bundledSkills = pkgs.lib.cleanSourceWith {
        src = ../skills;
        filter = path: _type:
          !(pkgs.lib.hasInfix "/index-cache/" path);
      };

      # Build the Vite/React web dashboard frontend.
      # Output lands in hermes_cli/web_dist which the FastAPI server serves
      # as a static SPA (see hermes_cli/web_server.py:WEB_DIST).
      hermesWeb = pkgs.buildNpmPackage {
        pname = "hermes-web";
        version = (builtins.fromTOML (builtins.readFile ../pyproject.toml)).project.version;
        src = ../web;
        npmDepsHash = "sha256-Y0pOzdFG8BLjfvCLmsvqYpjxFjAQabXp1i7X9W/cCU4=";
        # vite build writes to ../hermes_cli/web_dist relative to web/;
        # redirect into $out instead.
        postPatch = ''
          substituteInPlace vite.config.ts \
            --replace-warn '../hermes_cli/web_dist' "$out"
        '';
        installPhase = ''
          runHook preInstall
          npm run build
          runHook postInstall
        '';
        dontNpmBuild = true;  # we run the build in installPhase after substituteInPlace
      };

      # The venv's hermes_cli is in the read-only Nix store and lacks web_dist.
      # Create a thin overlay directory that shadows hermes_cli with web_dist
      # present, then prepend it via PYTHONPATH so Python finds it first.
      hermesSiteOverlay = pkgs.runCommand "hermes-site-overlay" { } ''
        venvSite=$(echo ${hermesVenv}/lib/python3.*/site-packages)
        mkdir -p $out/lib/hermes-overlay
        cp -rL --no-preserve=mode $venvSite/hermes_cli $out/lib/hermes-overlay/hermes_cli
        ln -s ${hermesWeb} $out/lib/hermes-overlay/hermes_cli/web_dist
      '';

      runtimeDeps = with pkgs; [
        nodejs_20 ripgrep git openssh ffmpeg tirith
      ];

      runtimePath = pkgs.lib.makeBinPath runtimeDeps;
    in {
      packages.default = pkgs.stdenv.mkDerivation {
        pname = "hermes-agent";
        version = (builtins.fromTOML (builtins.readFile ../pyproject.toml)).project.version;

        dontUnpack = true;
        dontBuild = true;
        nativeBuildInputs = [ pkgs.makeWrapper ];

        installPhase = ''
          runHook preInstall

          mkdir -p $out/share/hermes-agent $out/bin
          cp -r ${bundledSkills} $out/share/hermes-agent/skills

          ${pkgs.lib.concatMapStringsSep "\n" (name: ''
            makeWrapper ${hermesVenv}/bin/${name} $out/bin/${name} \
              --suffix PATH : "${runtimePath}" \
              --set HERMES_BUNDLED_SKILLS $out/share/hermes-agent/skills \
              --prefix PYTHONPATH : "${hermesSiteOverlay}/lib/hermes-overlay"
          '') [ "hermes" "hermes-agent" "hermes-acp" ]}

          runHook postInstall
        '';

        meta = with pkgs.lib; {
          description = "AI agent with advanced tool-calling capabilities";
          homepage = "https://github.com/NousResearch/hermes-agent";
          mainProgram = "hermes";
          license = licenses.mit;
          platforms = platforms.unix;
        };
      };
    };
}
