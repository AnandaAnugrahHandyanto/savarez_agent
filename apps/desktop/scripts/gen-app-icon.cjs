"use strict"

/**
 * Regenerates the desktop app icons (png / icns / ico) from the master art at
 * assets/icon-source.png, normalized to Apple's macOS icon grid so the dock
 * icon matches the size of every other app.
 *
 * The grid: on a 1024px canvas the icon body occupies ~824px (≈80%) centered,
 * leaving transparent padding. Shipping full-bleed art (body touching the
 * canvas edges) is what makes an icon render visibly larger than its peers in
 * the dock — macOS does NOT add the padding for you.
 *
 * Idempotent: the source is trimmed of any existing transparent margin before
 * the standard padding is applied, so re-running on already-padded art is a
 * no-op shape-wise.
 *
 * Requires ImageMagick (`magick`). On macOS `iconutil` produces a crisper
 * .icns; elsewhere we fall back to ImageMagick's icns writer.
 */

const fs = require("fs")
const os = require("os")
const path = require("path")
const { execFileSync } = require("child_process")

const ASSETS = path.resolve(__dirname, "..", "assets")
const SOURCE = path.join(ASSETS, "icon-source.png")

const CANVAS = 1024 // master canvas
const BODY = 824 // icon body within the canvas (Apple grid ≈ 80%)

// (size, scale) pairs for the .iconset iconutil consumes.
const ICONSET = [16, 32, 128, 256, 512].flatMap(s => [
  { name: `icon_${s}x${s}.png`, px: s },
  { name: `icon_${s}x${s}@2x.png`, px: s * 2 }
])

const ICO_SIZES = [16, 32, 48, 64, 128, 256]

function magick(args) {
  execFileSync("magick", args, { stdio: ["ignore", "pipe", "inherit"] })
}

function has(bin) {
  try {
    execFileSync(bin, ["--version"], { stdio: "ignore" })
    return true
  } catch {
    return false
  }
}

function padded(out) {
  // trim existing margin → fit body into BODY → center on transparent CANVAS.
  magick([
    SOURCE,
    "-trim",
    "+repage",
    "-resize",
    `${BODY}x${BODY}`,
    "-background",
    "none",
    "-gravity",
    "center",
    "-extent",
    `${CANVAS}x${CANVAS}`,
    out
  ])
}

function buildIcns(masterPng, outIcns) {
  if (has("iconutil")) {
    const set = fs.mkdtempSync(path.join(os.tmpdir(), "icon-")) + ".iconset"
    fs.mkdirSync(set, { recursive: true })
    for (const { name, px } of ICONSET) {
      magick([masterPng, "-resize", `${px}x${px}`, path.join(set, name)])
    }
    execFileSync("iconutil", ["-c", "icns", set, "-o", outIcns], { stdio: "inherit" })
    fs.rmSync(set, { recursive: true, force: true })
  } else {
    magick([masterPng, "-define", "icon:auto-resize=256,128,64,32,16", outIcns])
  }
}

function buildIco(masterPng, outIco) {
  magick([masterPng, "-define", `icon:auto-resize=${ICO_SIZES.join(",")}`, outIco])
}

function main() {
  if (!has("magick")) {
    console.error("[gen-app-icon] ImageMagick (`magick`) is required. `brew install imagemagick`.")
    process.exit(1)
  }
  if (!fs.existsSync(SOURCE)) {
    console.error(`[gen-app-icon] missing master art: ${path.relative(process.cwd(), SOURCE)}`)
    process.exit(1)
  }

  const png = path.join(ASSETS, "icon.png")
  padded(png)
  buildIcns(png, path.join(ASSETS, "icon.icns"))
  buildIco(png, path.join(ASSETS, "icon.ico"))

  console.log(`[gen-app-icon] regenerated icon.png/.icns/.ico (${BODY}px body on ${CANVAS}px canvas)`)
}

main()
