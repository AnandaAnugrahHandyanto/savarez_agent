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
  hacks = callPackage pyproject-nix.build.hacks { };

  overlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel";
  };

  # Keep the workspace locked through uv2nix, but supply the local voice stack
  # from nixpkgs so wheel-only transitive artifacts do not break evaluation.
  mkPrebuiltPassthru = dependencies: {
    inherit dependencies;
    optional-dependencies = { };
    dependency-groups = { };
  };

  pythonPackageOverrides = final: _prev: {
    numpy = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.numpy;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru { };
      };
    };

    av = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.av;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru { };
      };
    };

    humanfriendly = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.humanfriendly;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru { };
      };
    };

    coloredlogs = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.coloredlogs;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru {
          humanfriendly = [ ];
        };
      };
    };

    onnxruntime = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.onnxruntime;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru {
          coloredlogs = [ ];
          numpy = [ ];
          packaging = [ ];
        };
      };
    };

    ctranslate2 = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.ctranslate2;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru {
          numpy = [ ];
          pyyaml = [ ];
        };
      };
    };

    faster-whisper = hacks.nixpkgsPrebuilt {
      from = python311.pkgs.faster-whisper;
      prev = {
        nativeBuildInputs = [ final.pyprojectHook ];
        passthru = mkPrebuiltPassthru {
          av = [ ];
          ctranslate2 = [ ];
          huggingface-hub = [ ];
          onnxruntime = [ ];
          tokenizers = [ ];
          tqdm = [ ];
        };
      };
    };
  };

  pythonSet =
    (callPackage pyproject-nix.build.packages {
      python = python311;
    }).overrideScope
      (lib.composeManyExtensions [
        pyproject-build-systems.overlays.default
        overlay
        pythonPackageOverrides
      ]);
in
pythonSet.mkVirtualEnv "hermes-agent-env" {
  hermes-agent = [ "all" ];
}
