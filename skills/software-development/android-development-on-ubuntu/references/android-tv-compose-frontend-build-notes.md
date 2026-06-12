# Android TV Compose frontend-only build notes

Use this when the user wants an Android TV UI shell that must build successfully on Linux, but emulator/device testing is blocked (for example ADB offline or no KVM).

## Practical build-first strategy

1. Target the installed stable SDK on the machine and verify with local SDK contents before scaffolding.
2. Treat `./gradlew assembleDebug` as the acceptance gate.
3. Do not block progress on emulator boot/runtime validation when the user explicitly says not to require it.
4. Keep the app frontend-only: fake repository, mock channels, placeholder player/settings, no real IPTV links.
5. Generate the Gradle wrapper early and keep `local.properties` out of git.
6. After scaffolding, run `assembleDebug`, inspect the first real failure, fix it, and rerun until green.

## Known-good project shape

- Kotlin
- AGP 8.5.x
- Kotlin 1.9.24
- Java 17
- minSdk 23
- compile/target SDK 34 when that is the installed stable SDK on the machine
- Navigation Compose
- `androidx.tv:tv-material:1.0.0`
- `androidx.media3:media3-exoplayer`

## Real build pitfalls seen in session

### 1) TV app uses Compose Material3 icons/components but dependency is missing
If you import `androidx.compose.material3.Icon` for mobile bottom navigation or hybrid phone/TV shells, `material-icons-extended` alone is not enough. Add Compose Material3 explicitly:

```kotlin
implementation("androidx.compose.material3:material3")
```

Symptom:
- `Unresolved reference: Icon`
- imports compile for `Icons.Default.*` but the `Icon` composable itself does not resolve

### 2) Theme parent missing at resource link time
If `themes.xml` uses:

```xml
<style name="Theme.App" parent="Theme.Material3.DayNight.NoActionBar" />
```

then add the Material Components dependency or resource linking can fail:

```kotlin
implementation("com.google.android.material:material:1.12.0")
```

Symptom:
- `AAPT: error: resource style/Theme.Material3.DayNight.NoActionBar not found`

### 3) TV Material `ColorScheme` requires more fields than expected
When constructing `androidx.tv.material3.ColorScheme`, include:
- `surfaceTint`
- `inverseSurface`
- `inverseOnSurface`

Symptom:
- Kotlin compile errors saying no value passed for those parameters.

## UI structure pattern when emulator testing is deferred

For frontend-only IPTV or TV launcher style work, a good practical pattern is:
- use `BoxWithConstraints` to switch between compact phone UI and large-screen TV UI in the same composable tree
- keep TV mode focus-first with sidebar and larger cards
- wrap compact routes in a simple bottom-nav shell instead of reusing TV navigation literally
- keep Player/Settings responsive too, not just Home
- add a single preview entry file like `PreviewGallery.kt` so Android Studio inspection is one click

This lets the project stay buildable and reviewable even when ADB/emulator validation is unavailable.

## Delivery checklist for build-first Android TV tasks

- `./gradlew assembleDebug` prints `BUILD SUCCESSFUL`
- APK exists at `app/build/outputs/apk/debug/app-debug.apk`
- `.gitignore` excludes `local.properties`, `.gradle`, build outputs, signing files
- Git repo initialized with clean commits
- README documents Linux build path and explicitly notes emulator testing was deferred by request
