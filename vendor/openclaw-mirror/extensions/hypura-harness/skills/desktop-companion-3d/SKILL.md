---
name: hypura-desktop-companion-3d
description: Use Hypura Harness companion3d tools to drive the local browser or Electron 3D companion with local VRM, GLB, GLTF, or FBX assets.
category: automation, companion, threejs, avatar
version: 1.0.0
user-invocable: false
---

# Hypura Desktop Companion 3D

Use this skill when an agent should animate the local Desktop Companion instead
of writing to VRChat. Companion3D is a separate local browser or Electron
overlay layer. It does not inject FBX or VRM assets into VRChat.

## Required workflow

1. Inspect the companion runtime.

```text
hypura_harness_companion3d_status({})
```

2. Load only a user-approved local asset under the configured asset root.

```text
hypura_harness_companion3d_load_model({
  "model_path": "state/companion3d/assets/default.vrm"
})
```

Remote URLs are rejected. Path traversal and files outside
`state/companion3d/assets` are rejected. Prefer VRM, then GLB/GLTF, then FBX
when the asset has usable animation clips.

3. Drive state, emotion, speech, and gestures through structured events.

```text
hypura_harness_companion3d_event({
  "type": "emotion",
  "payload": {
    "emotion": "happy",
    "intensity": 0.75,
    "durationMs": 2400
  }
})
```

```text
hypura_harness_companion3d_set_state({
  "state": {
    "speaking": true,
    "fallbackFromVrchat": true
  }
})
```

## VRChat fallback rule

When the current VRChat avatar has no approved action profile, or when an
action is blocked by the safety gate, keep the VRChat layer idle and animate
only Companion3D. For speech, send `speak_start`, emotion, lip-sync state, and
`speak_end` to Companion3D; send VRChat actions only when an approved profile
contains the matching action.
