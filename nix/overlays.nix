# nix/overlays.nix
{ inputs, ... }:
{
  flake = {
    overlays.default = final: _: {
      hermes-agent = final.callPackage ./hermes-agent.nix {
        inherit (inputs) uv2nix pyproject-nix pyproject-build-systems;
      };
    };
  };
}
