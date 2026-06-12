# Android TV emulator stays `offline` on Ubuntu host without KVM

## Scenario
Ubuntu 24.04 host, Android TV x86 system image (`system-images;android-34;android-tv;x86`), emulator launches but `adb devices` never progresses beyond:

```text
emulator-5554    offline
```

## Verified host facts
- `emulator -accel-check` reported `/dev/kvm is not found`
- `/proc/cpuinfo` did not expose `vmx` or `svm`
- `adb offline` persisted for several minutes
- repeated probes after cold boot still showed `offline`

## Tried without success
- `-no-accel -gpu swiftshader_indirect`
- `-accel off -gpu swiftshader_indirect`
- `-no-snapshot-load -no-snapshot-save`
- `-wipe-data`
- restarting ADB server

## Interpretation
Do **not** report this as a working emulator verification just because the emulator process starts. This is a runtime boot failure / host limitation case.

The useful distinction is:
- **works:** SDK, AVD creation, emulator binary launch, Gradle build
- **not proven / failing:** guest boot reaching `adb device`

## Practical next moves
1. Prefer a real Android TV / Google TV device over ADB if available.
2. Enable virtualization in BIOS/UEFI and ensure `/dev/kvm` exists.
3. Only then retry x86/x86_64 Android TV emulators.
4. If forced to keep testing on the host, be explicit that software-mode emulator behavior is unreliable and slow.
