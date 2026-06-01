"use strict"

const fs = require("fs")
const path = require("path")

const root = path.resolve(__dirname, "..", "..", "..")

try {
  // En pnpm los workspaces symlinkean sus modulos locales o root.
  // Es mas seguro verificar que exista al menos UNA de las herramientas clave del workspace
  // en lugar de depender del hoisting global como lo hace npm.
  const isPnpmNodeModules = fs.existsSync(path.join(root, "node_modules", ".pnpm"))
  if (isPnpmNodeModules) {
    fs.accessSync(path.join(root, "node_modules", ".pnpm"))
  } else {
    fs.accessSync(path.join(root, "node_modules", "vite", "package.json"))
  }
} catch {
  // Determine package manager by lockfile existence
  const isPnpm = fs.existsSync(path.join(root, "pnpm-lock.yaml"))
  const pmCmd = isPnpm ? "pnpm install" : "npm ci"
  console.error(`Run from repo root: cd ${root} && ${pmCmd}`)
  process.exit(1)
}
