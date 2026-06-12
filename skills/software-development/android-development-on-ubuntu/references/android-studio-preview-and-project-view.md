# Android Studio preview and project-view notes

Use this when a build-first Android/Android TV UI task needs visual inspection in Android Studio but emulator/device execution is blocked or undesirable.

## Compose preview tactics that worked

1. Add `@Preview` composables for the important screens, not just one root activity.
2. Keep preview functions top-level and non-private. Android Studio was more reliable at finding them after removing `private`.
3. If per-screen files still feel annoying to open, create a `PreviewGallery.kt` with one public preview entry per screen (`SplashPreviewEntry`, `HomePreviewEntry`, etc.). That gives the user one obvious file to open.
4. For screens with side effects like delayed navigation, split the pure UI into a previewable helper composable (`SplashScreenContent`) and keep the effect (`LaunchedEffect`) in the runtime wrapper.
5. For viewmodel-backed screens, create a stateless content composable (`HomeScreenContent`) that accepts plain data so Preview does not depend on navigation/viewmodel plumbing.

## Android Studio UX fixes

If the user says they cannot find files that definitely exist on disk:
- switch the Project panel from `Android` view to `Project`
- use `Ctrl+Shift+N` for file search
- use double-Shift search for class/function search
- disable `Compact Middle Packages` in the Project tool window gear menu

## Reality check to tell the user

Compose Preview is good for:
- layout
- spacing
- colors
- card sizing
- basic visual review

Compose Preview is not a substitute for:
- D-pad navigation validation
- focus traversal behavior
- remote input testing
- actual TV runtime behavior
