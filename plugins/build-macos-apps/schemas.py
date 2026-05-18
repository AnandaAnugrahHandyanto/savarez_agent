"""Schemas for the build-macos-apps plugin."""

MACOS_INSPECT_PROJECT_SCHEMA = {
    "name": "macos_inspect_project",
    "description": (
        "Inspect a local macOS app repository for Xcode build containers. "
        "Reports .xcworkspace/.xcodeproj files, Swift Package hints, and the "
        "recommended container to use for scheme listing or builds."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path to inspect.",
            }
        },
        "required": ["path"],
    },
}

MACOS_LIST_SCHEMES_SCHEMA = {
    "name": "macos_list_schemes",
    "description": (
        "List Xcode schemes, targets, and configurations for a macOS project "
        "or workspace using xcodebuild -list -json."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path that contains the Xcode container.",
            },
            "container_path": {
                "type": "string",
                "description": "Optional explicit .xcworkspace or .xcodeproj path to use.",
            },
        },
        "required": ["path"],
    },
}

MACOS_BUILD_PROJECT_SCHEMA = {
    "name": "macos_build_project",
    "description": (
        "Build a local macOS Xcode scheme with xcodebuild. This Phase 1 tool "
        "performs an unsigned build only; it does not run tests, launch apps, "
        "or handle notarization."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path that contains the Xcode container.",
            },
            "scheme": {
                "type": "string",
                "description": "Xcode scheme to build.",
            },
            "container_path": {
                "type": "string",
                "description": "Optional explicit .xcworkspace or .xcodeproj path to use.",
            },
            "configuration": {
                "type": "string",
                "description": "Build configuration, usually Debug or Release.",
                "default": "Debug",
            },
            "destination": {
                "type": "string",
                "description": "xcodebuild destination string.",
                "default": "generic/platform=macOS",
            },
            "derived_data_path": {
                "type": "string",
                "description": "Optional DerivedData output path.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum build time before Hermes aborts the command.",
                "default": 1800,
                "minimum": 30,
                "maximum": 7200,
            },
        },
        "required": ["path", "scheme"],
    },
}

MACOS_TEST_PROJECT_SCHEMA = {
    "name": "macos_test_project",
    "description": (
        "Run xcodebuild test for a local macOS Xcode scheme. This Phase 2 "
        "tool adds test execution support without expanding into app launch, "
        "diagnostics, or signing workflows."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path that contains the Xcode container.",
            },
            "scheme": {
                "type": "string",
                "description": "Xcode scheme to test.",
            },
            "container_path": {
                "type": "string",
                "description": "Optional explicit .xcworkspace or .xcodeproj path to use.",
            },
            "configuration": {
                "type": "string",
                "description": "Test configuration, usually Debug.",
                "default": "Debug",
            },
            "destination": {
                "type": "string",
                "description": "xcodebuild destination string.",
                "default": "platform=macOS",
            },
            "test_plan": {
                "type": "string",
                "description": "Optional Xcode test plan name.",
            },
            "only_testing": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of -only-testing identifiers.",
            },
            "skip_testing": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of -skip-testing identifiers.",
            },
            "derived_data_path": {
                "type": "string",
                "description": "Optional DerivedData output path.",
            },
            "result_bundle_path": {
                "type": "string",
                "description": "Optional path for the generated .xcresult bundle.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum test time before Hermes aborts the command.",
                "default": 1800,
                "minimum": 30,
                "maximum": 7200,
            },
        },
        "required": ["path", "scheme"],
    },
}

MACOS_FIND_APP_BUNDLE_SCHEMA = {
    "name": "macos_find_app_bundle",
    "description": (
        "Find built .app bundles for a local macOS project. Prioritizes "
        "DerivedData and common build output locations to support local run loops."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path to inspect.",
            },
            "app_name": {
                "type": "string",
                "description": "Optional app name to filter matches, with or without the .app suffix.",
            },
            "configuration": {
                "type": "string",
                "description": "Preferred build configuration for ranking app bundle matches.",
                "default": "Debug",
            },
            "derived_data_path": {
                "type": "string",
                "description": "Optional explicit DerivedData path to search first.",
            },
        },
        "required": ["path"],
    },
}

MACOS_RUN_APP_SCHEMA = {
    "name": "macos_run_app",
    "description": (
        "Launch a local macOS app bundle with open. Supports explicit bundle "
        "paths or discovery via macos_find_app_bundle."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path used for app discovery.",
            },
            "app_bundle_path": {
                "type": "string",
                "description": "Optional explicit .app bundle path to launch.",
            },
            "app_name": {
                "type": "string",
                "description": "Optional app name used when discovering the bundle.",
            },
            "configuration": {
                "type": "string",
                "description": "Preferred build configuration for app discovery.",
                "default": "Debug",
            },
            "derived_data_path": {
                "type": "string",
                "description": "Optional explicit DerivedData path for bundle discovery.",
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional arguments passed after --args.",
            },
            "new_instance": {
                "type": "boolean",
                "description": "Launch a fresh app instance with open -n.",
                "default": False,
            },
            "activate": {
                "type": "boolean",
                "description": "Launch without foreground activation when false.",
                "default": True,
            },
            "wait_running_seconds": {
                "type": "integer",
                "description": "Seconds to poll for a running process after launch.",
                "default": 5,
                "minimum": 0,
                "maximum": 60,
            },
        },
        "required": ["path"],
    },
}

MACOS_STOP_APP_SCHEMA = {
    "name": "macos_stop_app",
    "description": (
        "Stop a local macOS app run loop. Attempts a graceful AppleScript quit "
        "first, then falls back to pkill when necessary."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository or project path used for app discovery.",
            },
            "app_bundle_path": {
                "type": "string",
                "description": "Optional explicit .app bundle path to stop.",
            },
            "app_name": {
                "type": "string",
                "description": "Optional app name used when discovering the bundle.",
            },
            "configuration": {
                "type": "string",
                "description": "Preferred build configuration for app discovery.",
                "default": "Debug",
            },
            "derived_data_path": {
                "type": "string",
                "description": "Optional explicit DerivedData path for bundle discovery.",
            },
            "force": {
                "type": "boolean",
                "description": "Escalate to SIGKILL if the app still appears to be running.",
                "default": False,
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Seconds to wait for the app to exit after a graceful quit.",
                "default": 15,
                "minimum": 0,
                "maximum": 60,
            },
        },
        "required": ["path"],
    },
}
