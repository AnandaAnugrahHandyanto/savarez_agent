# build-macos-apps

Bundled standalone Hermes plugin for local macOS app build workflows.

Current scope:

- inspect a repo for `.xcworkspace` / `.xcodeproj`
- list schemes through `xcodebuild -list -json`
- run unsigned `xcodebuild build`
- run `xcodebuild test`

Included toolset:

- `macos-dev`

Included tools:

- `macos_inspect_project`
- `macos_list_schemes`
- `macos_build_project`
- `macos_test_project`

What this plugin does not do yet:

- launch or stop apps
- collect logs or crash reports
- sign or notarize builds
- drive the UI or computer-use flows

Availability gate:

- only exposed when Hermes is running on macOS and `xcodebuild` is available in `PATH`

Build/test behavior:

- `macos_build_project` and `macos_test_project` disable signing by passing:
  - `CODE_SIGNING_ALLOWED=NO`
  - `CODE_SIGNING_REQUIRED=NO`
  - `CODE_SIGN_IDENTITY=`
- `macos_test_project` supports optional `test_plan`, `only_testing`, `skip_testing`, and `result_bundle_path`

Recommended flow:

1. `macos_inspect_project`
2. `macos_list_schemes`
3. `macos_build_project` or `macos_test_project`
