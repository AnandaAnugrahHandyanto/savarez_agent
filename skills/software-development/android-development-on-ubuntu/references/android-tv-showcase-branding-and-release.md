# Android TV frontend showcase: branding, screenshots, and release automation

Use this when an Android TV / hybrid TV+phone frontend already builds and the next step is making the repo presentable and distributable without depending on emulator validation.

## What worked well

### 1. Keep source branding separate from Android runtime assets
- Store editable source branding in a repo-visible folder such as:
  - `branding/app-icon.svg`
  - `branding/tv-banner.svg`
- Generate Android runtime assets as PNGs under:
  - `app/src/main/res/drawable-nodpi/`
- Wire the manifest to the PNG resources, not the SVG source files.

Example manifest attributes:

```xml
<application
    android:banner="@drawable/ic_tv_app_banner_png"
    android:icon="@drawable/ic_tv_app_icon_png"
    android:logo="@drawable/ic_tv_app_icon_png"
    android:roundIcon="@drawable/ic_tv_app_icon_png" />
```

Reason: Android app resources can use PNG launcher/banner assets directly, while SVGs remain better source-of-truth files for GitHub/README presentation and later export.

### 2. For public repo polish, add static showcase images even if emulator/device validation is blocked
- Put repo-facing visuals under `docs/assets/`
- SVG works well as editable source, but PNG screenshots are usually the safer README target for consistent GitHub rendering across clients
- A practical pattern is: keep editable source art in `branding/` or draft SVGs in `docs/assets/`, then export PNGs for the README
- Good starter set:
  - `docs/assets/home-tv.png`
  - `docs/assets/home-mobile.png`
  - `docs/assets/player-tv.png`

This is especially useful when:
- emulator is unreliable (`adb offline`, no KVM, etc.)
- the user mainly wants a clean public showcase now
- Compose previews exist locally but are not easy to surface on GitHub

### 3. Split CI into two workflows

#### Debug build workflow
Use a workflow like `.github/workflows/android-debug.yml` that:
- runs on push to `main`
- runs on pull requests
- supports manual trigger
- executes `./gradlew assembleDebug`
- uploads `app/build/outputs/apk/debug/app-debug.apk` as an artifact

#### Release workflow
Use a second workflow like `.github/workflows/android-release.yml` that:
- runs on tags matching `v*`
- supports manual `workflow_dispatch` with a tag input
- builds the debug APK
- creates or updates a GitHub Release
- attaches the APK via `softprops/action-gh-release@v2`

Manual release example:

```bash
git tag v1.0.0
git push origin v1.0.0
```

### 4. README should explain both local build and release flow
For Android frontend repos, README is stronger when it includes:
- CI badges for debug and release workflows
- branding section
- screenshot/showcase section
- exact local build command
- release instructions using tags
- preview entry points if Android Studio previews are important

## Pitfalls

1. `android:icon` / `android:banner` resource names must match the final generated asset filenames, not the source SVG names.
2. Keep editable SVG source files outside `app/src/main/res/` unless you are intentionally using VectorDrawable XML; raw `.svg` files are better treated as project assets, not Android resources.
3. GitHub screenshot sections should not depend on local absolute paths or Android Studio previews; generate repo-readable assets under `docs/assets/`.
4. If the project is frontend-only, be explicit that release artifacts are mock/demo APKs, not production streaming clients.

## Verified pattern from session
- Local build still passed with `./gradlew assembleDebug`
- APK artifact path remained:
  - `app/build/outputs/apk/debug/app-debug.apk`
- GitHub repo successfully used:
  - debug workflow for continuous verification
  - release workflow for tagged APK publishing
