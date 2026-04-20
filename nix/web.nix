# nix/web.nix — Hermes Web Dashboard (Vite/React) frontend build
{ pkgs, hermesNpmLib, ... }:
let
  src = ../web;
  npmDeps = pkgs.fetchNpmDeps {
    inherit src;
    hash = "sha256-Y0pOzdFG8BLjfvCLmsvqYpjxFjAQabXp1i7X9W/cCU4=";
  };

  npm = hermesNpmLib.mkNpmPassthru { folder = "web"; attr = "web"; pname = "hermes-web"; };
in
pkgs.buildNpmPackage (npm // {
  pname = "hermes-web";
  version = "0.0.0";
  inherit src npmDeps;

  doCheck = false;

  buildPhase = ''
    npx tsc -b
    npx vite build --outDir dist
  '';

  installPhase = ''
    runHook preInstall
    cp -r dist $out
    runHook postInstall
  '';
})
