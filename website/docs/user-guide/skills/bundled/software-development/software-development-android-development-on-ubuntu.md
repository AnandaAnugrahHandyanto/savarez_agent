---
title: "Android Development On Ubuntu"
sidebar_label: "Android Development On Ubuntu"
description: "Use when setting up or repairing an Android or Android TV Kotlin development environment on Ubuntu Linux, including Java, Android Studio, SDK tools, emulator..."
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Android Development On Ubuntu

Use when setting up or repairing an Android or Android TV Kotlin development environment on Ubuntu Linux, including Java, Android Studio, SDK tools, emulator, Gradle, ADB, environment variables, and verification.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/software-development/android-development-on-ubuntu` |
| Version | `1.0.0` |
| Author | Hermes Agent |
| License | MIT |
| Tags | `android`, `ubuntu`, `kotlin`, `android-studio`, `sdk`, `emulator`, `adb`, `gradle` |
| Related skills | [`sudo-from-secrets-file`](/docs/user-guide/skills/bundled/software-development/software-development-sudo-from-secrets-file), [`x11-desktop-automation`](/docs/user-guide/skills/bundled/software-development/software-development-x11-desktop-automation) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Hermes loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Android Development on Ubuntu

## Overview

This skill covers practical setup of a modern Android development environment on Ubuntu for Kotlin projects, including Android TV work. It is aimed at real machine setup, not theory: install the toolchain, wire shell environment variables, create or import a project, and verify Java, Gradle, ADB, SDK packages, and emulator behavior.

It also captures Ubuntu-specific pitfalls that waste time in practice: distro Gradle being too old for modern Android builds, manually installed Android command-line tools missing execute bits, and emulators being effectively unusable without KVM acceleration.

## When to Use

Use this when:
- setting up Android Studio + SDK on Ubuntu from a mostly clean machine
- preparing Kotlin Android or Android TV development
- verifying `adb`, `sdkmanager`, `avdmanager`, `emulator`, and Gradle on Linux
- making VS Code usable alongside Android Studio for Android source editing
- diagnosing why Android Emulator is slow or refuses acceleration on Linux

Do not use this for:
- Dockerized Android builds
- macOS or Windows Android setup
- React Native / Flutter specific setup workflows

## Default Ubuntu Setup Strategy

Prefer this stack on Ubuntu:
1. Install `openjdk-17-jdk`.
2. Install `adb` from apt for immediate platform-tools access.
3. Install Android Studio via Snap (`android-studio --classic`) unless the user explicitly wants the tarball/manual path.
4. Install Android SDK command-line tools manually under `~/Android/Sdk/cmdline-tools/latest`.
5. Accept licenses with `yes | sdkmanager --licenses`.
6. Install SDK packages via `sdkmanager` (`platform-tools`, platform, build-tools, emulator, system image).
7. Set shell environment in both `~/.profile` and the active interactive shell rc file (often `~/.zshrc` on Ubuntu desktops used by this user).
8. Use a modern Gradle distribution (8.x), not Ubuntu's ancient apt Gradle, for Android projects.

## Core Install Commands

### Base packages

```bash
sudo apt-get update
sudo apt-get install -y \
  openjdk-17-jdk \
  adb unzip wget curl \
  qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils
```

If you need a quick distro Gradle only as a bootstrap helper, you can install it:

```bash
sudo apt-get install -y gradle
```

But treat Ubuntu apt Gradle as potentially obsolete. For real Android work, install a modern Gradle distribution separately.

### Android Studio

```bash
sudo snap install android-studio --classic
```

Binary path after install is usually:

```bash
/snap/bin/android-studio
```

### Android command-line tools

Install under the standard user SDK path:

```bash
mkdir -p "$HOME/Android/Sdk/cmdline-tools"
cd /tmp
wget https://dl.google.com/android/repository/commandlinetools-linux-14742923_latest.zip
unzip commandlinetools-linux-14742923_latest.zip -d /tmp/android-cmdline-tools
mkdir -p "$HOME/Android/Sdk/cmdline-tools/latest"
cp -a /tmp/android-cmdline-tools/cmdline-tools/. "$HOME/Android/Sdk/cmdline-tools/latest/"
chmod +x "$HOME/Android/Sdk/cmdline-tools/latest/bin"/*
```

If using Python to install/extract instead of shell, verify the final layout is exactly:

```text
~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager
~/Android/Sdk/cmdline-tools/latest/bin/avdmanager
```

### Modern Gradle

Example with Gradle 8.10.2:

```bash
mkdir -p "$HOME/.local/gradle"
cd /tmp
wget https://services.gradle.org/distributions/gradle-8.10.2-bin.zip
unzip gradle-8.10.2-bin.zip
rm -rf "$HOME/.local/gradle/gradle-8.10.2"
mv /tmp/gradle-8.10.2 "$HOME/.local/gradle/gradle-8.10.2"
chmod +x "$HOME/.local/gradle/gradle-8.10.2/bin/gradle"
```

If the Gradle zip was extracted by Python or another non-shell path, explicitly verify the launcher is executable:

```bash
ls -l "$HOME/.local/gradle/gradle-8.10.2/bin/gradle"
"$HOME/.local/gradle/gradle-8.10.2/bin/gradle" -v
```

## Environment Variables

Write the same block into `~/.profile` and the active interactive shell rc file (`~/.zshrc` or `~/.bashrc`):

```bash
# >>> android-tv-dev >>>
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export GRADLE_HOME="$HOME/.local/gradle/gradle-8.10.2"
export ANDROID_SDK_ROOT="$HOME/Android/Sdk"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
export PATH="$GRADLE_HOME/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"
# <<< android-tv-dev <<<
```

Reload and verify:

```bash
source ~/.profile
source ~/.zshrc 2>/dev/null || true
hash -r
command -v java sdkmanager avdmanager adb emulator gradle
```

### Shell-specific verification pitfall

If your verification script is written in **bash**, do **not** blindly `source ~/.zshrc`. Real user `~/.zshrc` files often contain zsh-only syntax (`[[ ... ]]`, `${(%):-%n}`, plugin init, prompt logic) and will break bash-driven checks. In bash automation, source `~/.profile` and rely on it to publish exported environment, or conditionally source the shell rc that matches the current shell.

## SDK Package Installation

Accept licenses first:

```bash
yes | sdkmanager --licenses
```

Typical modern Android + Android TV package set:

```bash
sdkmanager \
  "platform-tools" \
  "platforms;android-34" \
  "build-tools;34.0.0" \
  "sources;android-34" \
  "emulator" \
  "system-images;android-34;android-tv;x86"
```

To discover TV-capable system images:

```bash
sdkmanager --list | grep 'system-images;android-.*;android-tv;'
```

## Android TV Emulator / AVD

Create an AVD:

```bash
echo "no" | avdmanager create avd \
  -n AndroidTV_API34 \
  -k "system-images;android-34;android-tv;x86" \
  -d tv_1080p
```

List AVDs:

```bash
emulator -list-avds
```

Run normally when KVM is available:

```bash
emulator -avd AndroidTV_API34
```

If KVM is unavailable, try software mode:

```bash
emulator -avd AndroidTV_API34 -no-accel -gpu swiftshader_indirect
```

or:

```bash
emulator -avd AndroidTV_API34 -accel off -gpu swiftshader_indirect
```

## Verification Workflow

### Java

```bash
java -version
```

Expect OpenJDK 17.

### SDK tools

```bash
sdkmanager --version
avdmanager list target
```

### ADB

```bash
adb kill-server
adb start-server
adb version
adb devices
```

### Emulator

In a second terminal after boot attempt:

```bash
adb wait-for-device
adb shell getprop ro.build.characteristics
```

For an Android TV emulator, expect TV-related characteristics.

Important distinction: **emulator process started** is not the same as **Android guest booted**. On Ubuntu hosts without KVM/virtualization, an Android TV x86 emulator may launch QEMU and still remain stuck as `adb devices -> offline` for many minutes. Report this as a runtime boot failure / unaccelerated-host limitation, not as a successful emulator verification.

### Gradle

Verify which Gradle is actually winning in PATH:

```bash
command -v gradle
gradle -v
```

If the output still shows an old distro version, explicitly export `GRADLE_HOME` and prepend its `bin` directory again, then `hash -r`.

## Creating a Minimal Kotlin Android TV Project

For a quick manual scaffold, create:
- root `settings.gradle.kts`
- root `build.gradle.kts`
- `gradle.properties`
- `local.properties`
- `app/build.gradle.kts`
- manifest with `LEANBACK_LAUNCHER`
- Kotlin `MainActivity`
- simple layout/resources

Key manifest pieces:

```xml
<uses-feature android:name="android.software.leanback" android:required="false" />
<uses-feature android:name="android.hardware.touchscreen" android:required="false" />
```

and activity category:

```xml
<category android:name="android.intent.category.LEANBACK_LAUNCHER" />
```

Then generate wrapper and build:

```bash
gradle wrapper --gradle-version 8.10.2
./gradlew --version
./gradlew assembleDebug
```

## VS Code Support

VS Code can edit Android/Kotlin projects fine, but Android Studio remains the stronger IDE for emulator/device and layout integration.

For build-first frontend work when emulator/device validation is blocked, prefer adding `@Preview` composables for important screens so the user can inspect layouts directly inside Android Studio without running the app.

When the project is moving from "it builds" to "it is presentable/public", add repo-facing assets too: keep editable branding in a top-level `branding/` folder (for example SVG source files), generate Android runtime icon/banner PNGs under `app/src/main/res/drawable-nodpi/`, and add README-friendly showcase images under `docs/assets/`.

Recommended extensions:

```bash
code --install-extension vscjava.vscode-java-pack --force
code --install-extension vscjava.vscode-gradle --force
code --install-extension fwcd.kotlin --force
```

Useful workspace settings:
- auto-import Gradle projects
- enable Kotlin language server
- hide `.gradle` and `build` directories from explorer noise

## Common Pitfalls

1. **Using Ubuntu apt Gradle as the real build Gradle.** On Ubuntu 24.04 it may be ancient (`4.4.1`) and unusable for modern Android Gradle Plugin versions. Install a modern Gradle separately or rely on the project wrapper.

2. **Frontend-only TV work with no usable emulator but no previews either.** If the host has ADB offline / no-KVM emulator problems, add Compose previews for Splash/Home/Player/Settings (or equivalent key screens) so the user can still inspect the UI in Android Studio. Static preview is not a substitute for D-pad validation, but it unblocks visual review.

3. **Hybrid phone + TV Compose UI with icons fails on `Unresolved reference: Icon`.** If the project uses `androidx.compose.material3.Icon` for a compact/mobile bottom bar, add:
   ```kotlin
   implementation("androidx.compose.material3:material3")
   ```
   `material-icons-extended` provides the icon vectors, not the Material3 `Icon` composable.

4. **Android Studio says `No preview found` even though `@Preview` exists.** Prefer top-level, non-private preview composables. If screen previews are awkward to discover, add a dedicated `PreviewGallery.kt` with one public preview entry per screen so the user can open a single file and inspect everything.

4. **User cannot find source files in Android Studio because of the Project panel mode.** When files definitely exist on disk, tell the user to switch the left panel from `Android` to `Project`, or use `Ctrl+Shift+N` / double-Shift search. `Compact Middle Packages` can hide the real folder tree and confuse people.

5. **Manual command-line tools extraction leaves non-executable binaries.** If `sdkmanager` says `Permission denied`, run:
   ```bash
   chmod +x "$HOME/Android/Sdk/cmdline-tools/latest/bin"/*
   ```

3. **Wrong cmdline-tools directory nesting.** `sdkmanager` must end up at `~/Android/Sdk/cmdline-tools/latest/bin/sdkmanager`, not `.../latest/cmdline-tools/bin/sdkmanager`.

4. **Assuming emulator verification is possible without KVM.** If `/dev/kvm` is missing or CPU virtualization flags (`vmx`/`svm`) are absent, hardware acceleration will not work. Expect software rendering, slow boots, or failure.

5. **Verifying the wrong shell state.** After writing `~/.profile` or `~/.zshrc`, open a fresh shell or re-source files before claiming PATH-based tools work.

6. **Assuming Android Studio installation also gives fully usable CLI SDK tools.** Studio may be installed, but `sdkmanager`, `avdmanager`, and emulator packages still need explicit SDK setup.

7. **Treating `adb offline` as success.** For emulator verification, `adb devices` must show the emulator as an online device or `adb shell` must respond. A long-running emulator process with `emulator-5554 offline` means the guest did not boot into a usable state.

8. **Bash automation sourcing `~/.zshrc`.** User shell config can contain zsh-only syntax and fail immediately when sourced from a bash verification script. Prefer `~/.profile` in bash-driven automation.

9. **Modern Gradle zip installed but launcher not executable.** If PATH points at `~/.local/gradle/gradle-8.10.2/bin/gradle` yet the shell still resolves `/usr/bin/gradle` or shows `Permission denied`, fix permissions with:
   ```bash
   chmod +x "$HOME/.local/gradle/gradle-8.10.2/bin/gradle"
   hash -r
   command -v gradle
   gradle -v
   ```

## References

- `references/android-tv-ubuntu-24-notes.md` — concrete Ubuntu 24 notes, package names, Gradle permission gotcha, shell verification pitfall, and emulator/KVM caveats from a live setup session.
- `references/android-tv-emulator-offline-no-kvm.md` — session-tested interpretation of the `emulator-5554 offline` failure mode on a no-KVM Ubuntu host, including what was tried and how to report it honestly.
- `references/android-tv-compose-frontend-build-notes.md` — build-first recipe for frontend-only Android TV Compose scaffolds when emulator/device validation is intentionally deferred; includes real dependency (`material`, `material3 Icon`) and `ColorScheme` pitfalls seen while driving `assembleDebug` to green.
- `references/android-tv-showcase-branding-and-release.md` — how to take a buildable Android TV frontend and make it presentable: SVG source branding, generated PNG launcher/banner assets, README showcase images, and split GitHub Actions debug/release workflows.
- `references/android-studio-preview-and-project-view.md` — preview-specific tactics: use top-level non-private `@Preview` composables, add a single `PreviewGallery.kt` entrypoint when needed, and help users switch Android Studio from `Android` view to `Project` when files seem missing.
- `scripts/verify-android-tv-dev.sh` — reusable end-to-end verification script for Java/SDK/Gradle/AVD/build checks; deliberately sources `~/.profile` only so bash automation does not choke on zsh-only rc syntax.

## Verification Checklist

- [ ] `java -version` shows OpenJDK 17
- [ ] `command -v sdkmanager avdmanager adb emulator gradle` resolves correctly
- [ ] `sdkmanager --licenses` completed
- [ ] required SDK packages installed (`platform-tools`, platform, build-tools, emulator, TV image)
- [ ] `adb version` works
- [ ] AVD exists and appears in `emulator -list-avds`
- [ ] emulator boot was attempted and acceleration mode noted honestly
- [ ] Gradle version is modern enough for AGP
- [ ] test project builds with `./gradlew assembleDebug`
- [ ] project opens in Android Studio and VS Code
