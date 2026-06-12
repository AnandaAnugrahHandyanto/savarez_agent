# Android TV setup notes on Ubuntu 24.04

Condensed notes from a live Ubuntu 24.04.4 setup session.

## Observed machine state that matters

- OS: Ubuntu 24.04.4 LTS
- Shell: `/usr/bin/zsh`
- VS Code already available as `/snap/bin/code`
- CPU virtualization flags count was `0`
- `/dev/kvm` was missing

Implication: Android Emulator hardware acceleration was not available. Any emulator verification on this host must be labeled as software-mode / unaccelerated unless KVM becomes available.

## Installed components used successfully

### apt

```bash
sudo apt-get install -y \
  openjdk-17-jdk gradle adb unzip wget curl \
  qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils
```

### snap

```bash
sudo snap install android-studio --classic
```

### manual Android cmdline-tools

Latest package URL used in the session:

```text
https://dl.google.com/android/repository/commandlinetools-linux-14742923_latest.zip
```

Installed into:

```text
~/Android/Sdk/cmdline-tools/latest
```

## Important practical findings

1. `sdkmanager` initially failed with `Permission denied` after manual extraction. Fix:

```bash
chmod +x "$HOME/Android/Sdk/cmdline-tools/latest/bin"/*
```

2. Ubuntu's apt `gradle -v` reported `Gradle 4.4.1`, which is too old for current Android Gradle Plugin usage.

3. A separate modern Gradle install was placed at:

```text
~/.local/gradle/gradle-8.10.2
```

The launcher also needed an executable bit after extraction:

```bash
chmod +x "$HOME/.local/gradle/gradle-8.10.2/bin/gradle"
```

4. In bash automation, sourcing the user's real `~/.zshrc` caused immediate failure because the file contains zsh-only syntax and prompt/plugin init. For bash verification scripts, source `~/.profile` instead of `~/.zshrc`.

5. Android TV system images were available via `sdkmanager --list`, including recent entries such as:

```text
system-images;android-34;android-tv;x86
system-images;android-36;android-tv;x86
system-images;android-36;android-tv;x86_64
```

6. Good base install set for Android TV work:

```bash
sdkmanager \
  "platform-tools" \
  "platforms;android-34" \
  "build-tools;34.0.0" \
  "sources;android-34" \
  "emulator" \
  "system-images;android-34;android-tv;x86"
```

7. The full verification chain succeeded up through project build:
- `adb version` worked
- required SDK packages were present
- `avdmanager create avd` succeeded for `AndroidTV_API34`
- `./gradlew assembleDebug` succeeded for the sample project
- APK output was created at `app/build/outputs/apk/debug/app-debug.apk`

8. Headless emulator launch on this host started QEMU but never reached a usable guest state; `adb devices` showed `emulator-5554 offline` even after several minutes. Treat this as an unaccelerated-host runtime limitation, not as emulator success.

## Verification commands worth reusing

```bash
java -version
sdkmanager --version
adb version
adb devices
command -v gradle
gradle -v
sdkmanager --list_installed
emulator -list-avds
```

## Honest reporting pattern

When KVM/virtualization is absent, do not claim emulator success just because packages installed. Report clearly:
- emulator packages may be installed
- AVD creation may succeed
- accelerated emulator is not available on this host
- software rendering may still be attempted with `-no-accel -gpu swiftshader_indirect`
