param(
  [string]$RunnerDir = "tmp\penpot-mcp-runner",
  [switch]$NoStart
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Runner = Join-Path $Root $RunnerDir
$PackageRoot = Join-Path $Runner "node_modules\@penpot\mcp"

New-Item -ItemType Directory -Force -Path $Runner | Out-Null

if (-not (Test-Path (Join-Path $Runner "package.json"))) {
  Set-Content -Path (Join-Path $Runner "package.json") -Value '{"private":true}' -Encoding UTF8
}

npm install --prefix $Runner "@penpot/mcp@stable"

$Workspace = Join-Path $PackageRoot "pnpm-workspace.yaml"
$WorkspaceText = Get-Content $Workspace -Raw
$WorkspaceText = $WorkspaceText -replace "esbuild: set this to true or false", "esbuild: true"
$WorkspaceText = $WorkspaceText -replace "sharp: set this to true or false", "sharp: true"
Set-Content -Path $Workspace -Value $WorkspaceText -Encoding UTF8

$RootPackage = Join-Path $PackageRoot "package.json"
$RootPackageText = Get-Content $RootPackage -Raw
$RootPackageText = $RootPackageText -replace '"build": "pnpm -r run build"', '"build": "corepack pnpm -r run build"'
$RootPackageText = $RootPackageText -replace '"build:multi-user": "pnpm -r run build:multi-user"', '"build:multi-user": "corepack pnpm -r run build:multi-user"'
$RootPackageText = $RootPackageText -replace '"start": "pnpm -r --parallel run start"', '"start": "corepack pnpm -r --parallel run start"'
$RootPackageText = $RootPackageText -replace '"start:multi-user": "pnpm -r --parallel run start:multi-user"', '"start:multi-user": "corepack pnpm -r --parallel run start:multi-user"'
$RootPackageText = $RootPackageText -replace '"bootstrap": "pnpm -r install && pnpm run build && pnpm run start"', '"bootstrap": "corepack pnpm -r install && corepack pnpm run build && corepack pnpm run start"'
$RootPackageText = $RootPackageText -replace '"bootstrap:multi-user": "pnpm -r install && pnpm run build && pnpm run start:multi-user"', '"bootstrap:multi-user": "corepack pnpm -r install && corepack pnpm run build && corepack pnpm run start:multi-user"'
Set-Content -Path $RootPackage -Value $RootPackageText -Encoding UTF8

$ServerPackage = Join-Path $PackageRoot "packages\server\package.json"
$ServerPackageText = Get-Content $ServerPackage -Raw
$ServerPackageText = $ServerPackageText -replace '"build": "pnpm run build:server && node scripts/copy-resources.js"', '"build": "corepack pnpm run build:server && node scripts/copy-resources.js"'
Set-Content -Path $ServerPackage -Value $ServerPackageText -Encoding UTF8

$PluginPackage = Join-Path $PackageRoot "packages\plugin\package.json"
$PluginPackageText = Get-Content $PluginPackage -Raw
$PluginPackageText = $PluginPackageText -replace '"start:multi-user": "pnpm run start"', '"start:multi-user": "corepack pnpm run start"'
Set-Content -Path $PluginPackage -Value $PluginPackageText -Encoding UTF8

if ($NoStart) {
  Write-Output "Prepared Penpot MCP runner at $Runner"
  exit 0
}

$Log = Join-Path $Runner "penpot-mcp-bg.log"
$Command = "cd /d `"$Runner`" && set PATH=C:\Program Files\nodejs;%PATH% && node .\node_modules\@penpot\mcp\bin\mcp-local.js >> `"$Log`" 2>>&1"
cmd.exe /c start "Penpot MCP" /min cmd.exe /c $Command

Start-Sleep -Seconds 5
Write-Output "Penpot MCP launch requested."
Write-Output "Plugin UI: http://localhost:4400/"
Write-Output "MCP endpoint: http://localhost:4401/mcp"
Write-Output "Log: $Log"
