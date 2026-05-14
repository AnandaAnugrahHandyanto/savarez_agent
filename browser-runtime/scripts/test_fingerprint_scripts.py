from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SESSION_FIXTURE = SCRIPTS / "fixtures" / "fingerprint_probe_session_fixture.json"
RAW_FIXTURE = SCRIPTS / "fixtures" / "fingerprint_probe_raw_fixture.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def assert_no_shareable_secrets(report: dict) -> None:
    text = json.dumps(report, sort_keys=True)
    forbidden = [
        "devtools/browser/raw-capability",
        "fake-sensitive-token",
        "192.168.1.20",
        "8.8.8.8",
        "laptop.local",
        "relay.example.net",
        "Authorization",
        "cookie=",
        "runtime-data/profiles",
    ]
    for value in forbidden:
        assert value not in text


def test_probe_fixture_builds_minimum_sanitized_schema_without_raw_capabilities():
    probe = load_module("fingerprint_probe", SCRIPTS / "fingerprint_probe.py")
    session = json.loads(SESSION_FIXTURE.read_text())
    raw = json.loads(RAW_FIXTURE.read_text())

    report = probe.build_sanitized_report(
        raw,
        session,
        mode="local-deterministic",
        generated_at_utc="2026-05-11T00:00:00+00:00",
    )

    assert report["schema_version"] == "hbr.p4.fingerprint_probe.v1"
    assert report["measurement_contract_version"] == "hbr.p5.direct_probe.v1"
    assert report["measurement_completeness"]["complete"] is True
    assert report["measurement_completeness"]["unavailable_contexts"] == {}
    assert report["runtime"]["chrome_product_major"] == "143"
    assert report["policy"] == {
        "webrtc_ip_policy": "default_public_interface_only",
        "gpu_policy": "auto",
    }
    assert report["persona"]["viewport"] == {"width": 1280, "height": 800}
    assert report["identity"]["coherent"] is True
    assert report["identity"]["ua_major"] == "143"
    assert report["identity"]["ua_ch_major"] == "143"
    assert report["identity"]["mismatches"] == []
    assert set(report["contexts"]) == {"top", "iframe", "worker", "popup"}
    assert report["webrtc"] == {
        "candidate_classes": ["mdns_host", "private_literal", "public_srflx", "relay"],
        "raw_values_redacted": True,
    }
    assert report["rendering"]["webgl"]["renderer_class"] == "swiftshader"
    assert report["red_flags"] == ["webgl_swiftshader"]
    assert_no_shareable_secrets(report)


def p4_surface_raw_fixture() -> dict:
    raw = copy.deepcopy(json.loads(RAW_FIXTURE.read_text()))
    ua_data = raw["uaData"]
    for name in ("top", "iframe", "popup"):
        context = raw["contexts"][name]
        context.setdefault("screen", {"width": 1280, "height": 800, "availWidth": 1280, "availHeight": 800})
        context["uaData"] = ua_data
        context["hardware"] = {"hardwareConcurrency": 8, "deviceMemory": 8, "maxTouchPoints": 0}
        context["window"] = {"outerWidth": 1280, "outerHeight": 800}
        context["visualViewport"] = {"width": 1280, "height": 800, "scale": 1}
        context["matchMedia"] = {
            "screenExact": True,
            "minWidth": True,
            "maxWidth": True,
            "pointerFine": True,
            "hoverHover": True,
        }
    raw["contexts"]["worker"]["hardware"] = {"hardwareConcurrency": 8, "deviceMemory": 8, "maxTouchPoints": 0}
    raw["service_worker_status"] = {
        "status": "residual",
        "reason": "service_worker_probe_not_attempted_in_local_fixture",
    }
    return raw


def test_probe_reports_p4_s1_coherence_surfaces_and_service_worker_residual():
    probe = load_module("fingerprint_probe_p4_surfaces", SCRIPTS / "fingerprint_probe.py")
    session = json.loads(SESSION_FIXTURE.read_text())
    raw = p4_surface_raw_fixture()

    report = probe.build_sanitized_report(
        raw,
        session,
        mode="local-deterministic",
        generated_at_utc="2026-05-11T00:00:00+00:00",
    )

    top = report["contexts"]["top"]
    assert top["hardware"] == {"hardware_concurrency": 8, "device_memory_gb": 8, "max_touch_points": 0}
    assert top["window"] == {"outer_width": 1280, "outer_height": 800}
    assert top["visual_viewport"] == {"width": 1280, "height": 800, "scale": 1}
    assert top["match_media"]["screen_exact"] is True
    assert report["service_worker"]["status"] == "residual"
    assert report["service_worker"]["reason"] == "service_worker_probe_not_attempted_in_local_fixture"
    assert report["surface_coherence"]["coherent"] is True
    assert report["surface_coherence"]["mismatches"] == []
    touched = set(report["surface_coherence"]["touched_surfaces"])
    assert {
        "navigator.hardwareConcurrency",
        "navigator.deviceMemory",
        "navigator.maxTouchPoints",
        "window.visualViewport",
        "window.matchMedia",
        "serviceWorker.status",
    } <= touched
    assert any("Service-worker coherence" in risk for risk in report["residual_risks"])
    assert_no_shareable_secrets(report)


def test_probe_flags_p4_s1_surface_mismatch_without_leaking_raw_values():
    probe = load_module("fingerprint_probe_p4_mismatch", SCRIPTS / "fingerprint_probe.py")
    session = json.loads(SESSION_FIXTURE.read_text())
    raw = p4_surface_raw_fixture()
    raw["contexts"]["worker"]["hardware"]["hardwareConcurrency"] = 16

    report = probe.build_sanitized_report(
        raw,
        session,
        mode="local-deterministic",
        generated_at_utc="2026-05-11T00:00:00+00:00",
    )

    assert report["surface_coherence"]["coherent"] is False
    assert "surface_incoherent" in report["red_flags"]
    assert any("navigator.hardwareConcurrency" in item for item in report["surface_coherence"]["mismatches"])
    assert_no_shareable_secrets(report)


def test_probe_cli_writes_strict_sanitized_fixture_output(tmp_path: Path):
    out = tmp_path / "fingerprint-probe.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "fingerprint_probe.py"),
            "--session-json",
            str(SESSION_FIXTURE),
            "--fixture-json",
            str(RAW_FIXTURE),
            "--out",
            str(out),
            "--mode",
            "local-deterministic",
            "--strict",
        ],
        cwd=SCRIPTS.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = json.loads(result.stdout)
    assert stdout["measurement_complete"] is True
    assert stdout["unavailable_contexts"] == {}
    report = json.loads(out.read_text())
    assert report["identity"]["coherent"] is True
    assert_no_shareable_secrets(report)


def test_probe_marks_missing_popup_as_legacy_unknown_not_p5_signoff():
    probe = load_module("fingerprint_probe_missing_popup", SCRIPTS / "fingerprint_probe.py")
    session = json.loads(SESSION_FIXTURE.read_text())
    raw = copy.deepcopy(json.loads(RAW_FIXTURE.read_text()))
    raw["contexts"].pop("popup")

    report = probe.build_sanitized_report(
        raw,
        session,
        mode="local-deterministic",
        generated_at_utc="2026-05-11T00:00:00+00:00",
    )

    popup = report["contexts"]["popup"]
    assert popup["measured"] is False
    assert popup["availability"]["status"] == "legacy_unknown"
    assert popup["availability"]["reason"] == "context_absent_without_availability_metadata_not_p5_signoff"
    assert report["measurement_completeness"]["complete"] is False
    assert report["measurement_completeness"]["contexts"]["popup"] == {
        "measured": False,
        "status": "legacy_unknown",
        "reason": "context_absent_without_availability_metadata_not_p5_signoff",
    }
    assert "popup" in report["measurement_completeness"]["unavailable_contexts"]


def test_probe_cli_strict_writes_report_before_failing_on_incomplete_measurement(tmp_path: Path):
    raw = copy.deepcopy(json.loads(RAW_FIXTURE.read_text()))
    raw["contexts"].pop("popup")
    raw_path = tmp_path / "raw-missing-popup.json"
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    out = tmp_path / "fingerprint-probe.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "fingerprint_probe.py"),
            "--session-json",
            str(SESSION_FIXTURE),
            "--fixture-json",
            str(raw_path),
            "--out",
            str(out),
            "--mode",
            "local-deterministic",
            "--strict",
        ],
        cwd=SCRIPTS.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert out.exists(), result.stdout + result.stderr
    stdout = json.loads(result.stdout)
    assert stdout["measurement_complete"] is False
    assert stdout["unavailable_contexts"]["popup"]["status"] == "legacy_unknown"
    report = json.loads(out.read_text())
    assert report["measurement_completeness"]["complete"] is False


def test_live_probe_runtime_evaluate_uses_user_gesture_for_popup_contract():
    source = (SCRIPTS / "fingerprint_probe.py").read_text(encoding="utf-8")
    assert '"userGesture": True' in source
    assert "cdp_runtime_evaluate_user_gesture" in source


def test_compare_reports_marks_identity_coherence_improved_without_undetectable_claims(tmp_path: Path):
    compare = load_module("fingerprint_compare", SCRIPTS / "fingerprint_compare.py")
    before = {
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "identity": {"coherent": False, "mismatches": ["ua_major 125 != ua_ch_major 143"]},
        "red_flags": ["identity_incoherent", "webgl_swiftshader"],
        "webrtc": {"candidate_classes": ["private_literal"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "swiftshader"}},
        "residual_risks": ["public detector pages not measured in this local fixture"],
    }
    after = {
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "identity": {"coherent": True, "mismatches": []},
        "red_flags": ["webgl_swiftshader"],
        "webrtc": {"candidate_classes": ["mdns_host", "public_srflx"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "swiftshader"}},
        "residual_risks": ["public detector pages not measured in this local fixture"],
    }

    delta = compare.compare_reports(before, after)
    markdown = compare.render_markdown(delta)

    assert delta["identity_coherence"] == "improved"
    assert delta["red_flags"]["resolved"] == ["identity_incoherent"]
    assert "undetectable" not in markdown.lower()
    assert "identity coherence: improved" in markdown
    assert "Public detector pages are evidence only" in markdown


def test_compare_cli_writes_markdown_and_json_delta(tmp_path: Path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    out = tmp_path / "p4-risk-delta.md"
    json_out = tmp_path / "p4-risk-delta.json"
    before.write_text(json.dumps({
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "identity": {"coherent": False, "mismatches": ["HeadlessChrome marker present"]},
        "red_flags": ["identity_incoherent", "headless_user_agent"],
        "webrtc": {"candidate_classes": ["private_literal"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "blocked"}},
        "residual_risks": [],
    }))
    after.write_text(json.dumps({
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "identity": {"coherent": True, "mismatches": []},
        "red_flags": [],
        "webrtc": {"candidate_classes": ["mdns_host"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "hardware_like"}},
        "residual_risks": [],
    }))

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "fingerprint_compare.py"),
            "--before",
            str(before),
            "--after",
            str(after),
            "--out",
            str(out),
            "--json-out",
            str(json_out),
        ],
        cwd=SCRIPTS.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "identity coherence: improved" in out.read_text()
    delta = json.loads(json_out.read_text())
    assert delta["red_flags"]["resolved"] == ["headless_user_agent", "identity_incoherent"]


def test_compare_reports_surface_coherence_improved_without_undetectable_claims():
    compare = load_module("fingerprint_compare_p4_surfaces", SCRIPTS / "fingerprint_compare.py")
    before = {
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "identity": {"coherent": True, "mismatches": []},
        "surface_coherence": {"coherent": False, "mismatches": ["navigator.hardwareConcurrency differs across top, worker"]},
        "red_flags": ["surface_incoherent"],
        "webrtc": {"candidate_classes": ["mdns_host"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "swiftshader"}},
        "residual_risks": [],
    }
    after = {
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "identity": {"coherent": True, "mismatches": []},
        "surface_coherence": {"coherent": True, "mismatches": []},
        "red_flags": [],
        "webrtc": {"candidate_classes": ["mdns_host"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "swiftshader"}},
        "residual_risks": [],
    }

    delta = compare.compare_reports(before, after)
    markdown = compare.render_markdown(delta)

    assert delta["surface_coherence"]["delta"] == "improved"
    assert delta["surface_coherence"]["after"]["coherent"] is True
    assert "surface coherence: improved" in markdown
    assert "undetectable" not in markdown.lower()


P4_BASELINE_PUBLIC_DETECTOR_SLUGS = [
    "browserleaks-ip",
    "browserleaks-dns",
    "browserleaks-webrtc",
    "browserleaks-canvas",
    "browserleaks-webgl",
    "browserleaks-fonts",
    "browserleaks-javascript",
    "browserleaks-tls",
    "creepjs",
    "sannysoft",
    "pixelscan-fingerprint",
    "pixelscan-bot",
]


def write_public_detector_manifest(path: Path, slugs: list[str]) -> None:
    path.mkdir()
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"attempted": len(slugs), "captured": len(slugs), "nonblank": len(slugs)},
                "detectors": [{"slug": slug, "ok": True, "screenshot": {"nonblank": True}} for slug in slugs],
            }
        ),
        encoding="utf-8",
    )


def test_public_detector_capture_default_tests_match_p4_baseline_browserleaks_coverage():
    capture = load_module("public_detector_capture_defaults", SCRIPTS / "public_detector_capture.py")

    slugs = [test["slug"] for test in capture.DEFAULT_TESTS]

    assert slugs == P4_BASELINE_PUBLIC_DETECTOR_SLUGS
    assert len(slugs) == len(set(slugs))


def test_public_detector_compare_default_capture_slugs_have_no_coverage_delta(tmp_path: Path):
    capture = load_module("public_detector_capture_compare_defaults", SCRIPTS / "public_detector_capture.py")
    public_compare = load_module("public_detector_compare_default_slugs", SCRIPTS / "public_detector_compare.py")
    before = tmp_path / "before"
    after = tmp_path / "after"
    write_public_detector_manifest(before, P4_BASELINE_PUBLIC_DETECTOR_SLUGS)
    write_public_detector_manifest(after, [test["slug"] for test in capture.DEFAULT_TESTS])

    comparison = public_compare.compare_runs(before, after, redact=True)

    verdicts = {row["detector"]: row["verdict"] for row in comparison["detectors"]}
    assert "browserleaks-javascript" in verdicts
    assert "fpscanner" not in verdicts
    assert set(verdicts.values()) == {"unchanged"}


def test_public_detector_capture_manifest_redacts_and_counts(tmp_path: Path):
    capture = load_module("public_detector_capture", SCRIPTS / "public_detector_capture.py")
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()
    shot = screenshots / "01-sannysoft.png"
    from PIL import Image

    image = Image.new("RGB", (4, 4), color="white")
    image.putpixel((0, 0), (0, 0, 0))
    image.save(shot)
    results = [
        {
            "slug": "sannysoft",
            "title": "bot.sannysoft",
            "url": "https://bot.sannysoft.com/",
            "ok": True,
            "screenshot": {"path": str(shot)},
            "detector_summary": {
                "interesting_lines": [
                    "Public IP Address 8.8.8.8",
                    "JA3 Hash b58d08763b56d3133c6936d45dd65ffc",
                    "ws://127.0.0.1:9222/devtools/browser/raw-capability token=fake cookie=secret",
                ]
            },
        }
    ]

    manifest = capture.build_manifest(tmp_path, results, config={"bind": "127.0.0.1:7793"})

    assert manifest["counts"] == {"attempted": 1, "captured": 1, "nonblank": 1}
    text = json.dumps(manifest, sort_keys=True)
    for forbidden in ["8.8.8.8", "b58d08763b56d3133c6936d45dd65ffc", "devtools/browser", "token=fake", "cookie=secret"]:
        assert forbidden not in text
    assert manifest["detectors"][0]["detector_summary"]["interesting_lines"][0] == "Public IP Address [REDACTED_IP]"


def test_public_detector_capture_manifest_canonicalizes_sensitive_screenshot_paths(tmp_path: Path):
    capture = load_module("public_detector_capture_sensitive_path", SCRIPTS / "public_detector_capture.py")
    sensitive_dir = tmp_path / "runtime-data" / "profiles" / "profile-token=fake-cookie=secret"
    sensitive_dir.mkdir(parents=True)
    detector_hash = "0123456789abcdef0123456789abcdef"
    shot = sensitive_dir / f"Authorization:Bearer-secret-8.8.8.8-{detector_hash}.png"
    from PIL import Image

    image = Image.new("RGB", (4, 4), color="white")
    image.putpixel((0, 0), (0, 0, 0))
    image.save(shot)

    manifest = capture.build_manifest(
        tmp_path,
        [
            {
                "slug": "sannysoft",
                "title": "bot.sannysoft",
                "url": "https://bot.sannysoft.com/",
                "ok": True,
                "screenshot": {"path": str(shot)},
            }
        ],
    )

    screenshot = manifest["detectors"][0]["screenshot"]
    assert screenshot["exists"] is True
    assert screenshot["nonblank"] is True
    text = json.dumps(manifest, sort_keys=True)
    for forbidden in [
        "8.8.8.8",
        detector_hash,
        "token=fake",
        "cookie=secret",
        "Authorization",
        "runtime-data/profiles",
        "profile-token",
    ]:
        assert forbidden not in text


def test_public_detector_capture_cli_accepts_ops_contract_and_redacts_manifest(tmp_path: Path):
    screenshots = tmp_path / "screenshots"
    screenshots.mkdir()
    shot = screenshots / "01-sannysoft.png"
    from PIL import Image

    image = Image.new("RGB", (4, 4), color="white")
    image.putpixel((0, 0), (0, 0, 0))
    image.save(shot)
    results = tmp_path / "detector-results.json"
    results.write_text(
        json.dumps(
            [
                {
                    "slug": "sannysoft",
                    "title": "bot.sannysoft",
                    "url": "https://bot.sannysoft.com/",
                    "ok": True,
                    "screenshot": {"path": str(shot)},
                    "detector_summary": {
                        "interesting_lines": [
                            "Public IP Address 8.8.8.8",
                            "JA3 Hash b58d08763b56d3133c6936d45dd65ffc",
                            "ws://127.0.0.1:9222/devtools/browser/raw-capability token=fake cookie=secret",
                            "profile path /home/fixture/.hermes/hermes-agent/browser-runtime/runtime-data/profiles/profile-a",
                        ]
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "run"
    manifest = out_dir / "manifest.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "public_detector_capture.py"),
            "--session-json",
            str(SESSION_FIXTURE),
            "--out-dir",
            str(out_dir),
            "--results-json",
            str(results),
            "--manifest",
            str(manifest),
            "--viewport-width",
            "1440",
            "--viewport-height",
            "1000",
            "--max-height",
            "12000",
            "--strict-nonblank",
        ],
        cwd=SCRIPTS.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    written = json.loads(manifest.read_text())
    assert written["counts"] == {"attempted": 1, "captured": 1, "nonblank": 1}
    assert written["config"] == {
        "max_height": 12000,
        "source": "results_json",
        "strict_nonblank": True,
        "viewport_height": 1000,
        "viewport_width": 1440,
    }
    text = json.dumps(written, sort_keys=True)
    for forbidden in [
        "8.8.8.8",
        "b58d08763b56d3133c6936d45dd65ffc",
        "devtools/browser",
        "token=fake",
        "cookie=secret",
        "/home/fixture",
        "runtime-data/profiles",
    ]:
        assert forbidden not in text


def test_public_detector_compare_reports_counts_verdicts_and_redacts(tmp_path: Path):
    public_compare = load_module("public_detector_compare", SCRIPTS / "public_detector_compare.py")
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"attempted": 2, "captured": 1, "nonblank": 1},
                "detectors": [
                    {"slug": "sannysoft", "ok": False, "error": "blocked with ip 8.8.8.8"},
                    {"slug": "creepjs", "ok": True, "detector_summary": {"interesting_lines": ["old hash 0123456789abcdef0123456789abcdef"]}},
                ],
            }
        ),
        encoding="utf-8",
    )
    (after / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"attempted": 2, "captured": 2, "nonblank": 2},
                "detectors": [
                    {"slug": "sannysoft", "ok": True, "detector_summary": {"signals": {"webdriver": "missing"}}},
                    {"slug": "creepjs", "ok": True, "detector_summary": {"interesting_lines": ["same public ip 8.8.8.8"]}},
                ],
            }
        ),
        encoding="utf-8",
    )

    comparison = public_compare.compare_runs(before, after, redact=True)
    markdown = public_compare.render_markdown(comparison)

    assert comparison["before"]["counts"] == {"attempted": 2, "captured": 1, "nonblank": 1}
    assert comparison["after"]["counts"] == {"attempted": 2, "captured": 2, "nonblank": 2}
    verdicts = {row["detector"]: row["verdict"] for row in comparison["detectors"]}
    assert verdicts["sannysoft"] == "improved"
    assert verdicts["creepjs"] == "unchanged"
    text = json.dumps(comparison, sort_keys=True) + markdown
    for forbidden in ["8.8.8.8", "0123456789abcdef0123456789abcdef", "devtools/browser", "token=fake", "cookie=secret"]:
        assert forbidden not in text
    assert "universal" not in markdown.lower()
    assert "undetectable" not in markdown.lower()


def test_public_detector_compare_cli_accepts_architecture_redact_flag(tmp_path: Path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"attempted": 1, "captured": 0, "nonblank": 0},
                "detectors": [{"slug": "sannysoft", "ok": False, "error": "ip 8.8.8.8"}],
            }
        ),
        encoding="utf-8",
    )
    (after / "manifest.json").write_text(
        json.dumps(
            {
                "counts": {"attempted": 1, "captured": 1, "nonblank": 1},
                "detectors": [
                    {
                        "slug": "sannysoft",
                        "ok": True,
                        "detector_summary": {
                            "interesting_lines": ["hash 0123456789abcdef0123456789abcdef"],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "comparison.md"
    json_out = tmp_path / "comparison.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "public_detector_compare.py"),
            "--before",
            str(before),
            "--after",
            str(after),
            "--out",
            str(out),
            "--json-out",
            str(json_out),
            "--redact",
        ],
        cwd=SCRIPTS.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    comparison = json.loads(json_out.read_text())
    assert comparison["raw_values_redacted"] is True
    text = out.read_text() + json.dumps(comparison, sort_keys=True)
    for forbidden in ["8.8.8.8", "0123456789abcdef0123456789abcdef"]:
        assert forbidden not in text


def test_public_detector_compare_replaces_sensitive_input_path_labels(tmp_path: Path):
    detector_hash = "fedcba9876543210fedcba9876543210"
    before = tmp_path / f"before-token=fake-cookie=secret-8.8.8.8-{detector_hash}"
    after = tmp_path / "after-Authorization:Bearer-secret-192.0.2.99-devtools-browser"
    before.mkdir()
    after.mkdir()
    manifest = {
        "counts": {"attempted": 1, "captured": 1, "nonblank": 1},
        "detectors": [{"slug": "sannysoft", "ok": True}],
    }
    (before / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (after / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "comparison.md"
    json_out = tmp_path / "comparison.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "public_detector_compare.py"),
            "--before",
            str(before),
            "--after",
            str(after),
            "--out",
            str(out),
            "--json-out",
            str(json_out),
            "--redact",
        ],
        cwd=SCRIPTS.parent,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    comparison = json.loads(json_out.read_text())
    assert comparison["before"]["label"] == "before"
    assert comparison["after"]["label"] == "after"
    text = out.read_text() + json.dumps(comparison, sort_keys=True)
    for forbidden in [
        "8.8.8.8",
        "192.0.2.99",
        detector_hash,
        "token=fake",
        "cookie=secret",
        "Authorization",
        "devtools-browser",
    ]:
        assert forbidden not in text


def test_internal_artifact_sanitizer_manifest_is_explicitly_internal_only(tmp_path: Path):
    hygiene = load_module("artifact_hygiene_internal", SCRIPTS / "artifact_hygiene_scan.py")
    source = tmp_path / "source"
    dest = tmp_path / "internal-sanitized"
    source.mkdir()
    (source / "detector-output.json").write_text(
        json.dumps(
            {
                "capability": "ws://127.0.0.1:9222/devtools/browser/raw-capability",
                "takeover": "http://127.0.0.1:7788/takeover/session?token=fake-sensitive-token",
            }
        ),
        encoding="utf-8",
    )

    manifest = hygiene.sanitize_bundle(source, dest, tier="internal-sanitized")

    assert manifest["scan_tier"] == "internal-sanitized"
    assert manifest["sensitivity_tier"] == "internal_sanitized"
    assert manifest["public_share_safe"] is False
    written = json.loads((dest / "SANITIZED-MANIFEST.json").read_text())
    assert written["policy"]["audience"] == "internal_review_only"


def test_public_redacted_sanitizer_writes_whitelist_only_bundle_and_strict_scan(tmp_path: Path):
    source = tmp_path / "raw-source"
    dest = tmp_path / "public-redacted"
    source.mkdir()
    detector_hash = "0123456789abcdef0123456789abcdef"
    safe_probe = {
        "schema_version": "hbr.p4.fingerprint_probe.v1",
        "measurement_contract_version": "hbr.p5.direct_probe.v1",
        "measurement_completeness": {
            "complete": True,
            "contexts": {
                "top": {"measured": True, "status": "measured"},
                "iframe": {"measured": True, "status": "measured"},
                "worker": {"measured": True, "status": "measured"},
                "popup": {"measured": True, "status": "measured"},
            },
            "unavailable_contexts": {},
        },
        "identity": {"coherent": True, "mismatches": []},
        "contexts": {
            "popup": {"measured": True, "ua_major": "143", "platform": "MacIntel", "timezone": "America/New_York"}
        },
        "webrtc": {"candidate_classes": ["public_srflx"], "raw_values_redacted": True},
        "rendering": {"webgl": {"renderer_class": "swiftshader"}},
        "red_flags": ["webgl_swiftshader"],
        "residual_risks": ["raw public detector details stay internal"],
    }
    (source / "fingerprint-probe.json").write_text(json.dumps(safe_probe), encoding="utf-8")
    (source / "raw-detector-output.json").write_text(
        "\n".join(
            [
                "public ip 8.8.8.8",
                "candidate:842163049 1 udp 1677729535 8.8.8.8 56144 typ srflx raddr 192.168.1.20 rport 56143",
                f"detector hash {detector_hash}",
                "runtime path /home/fixture/.hermes/hermes-agent/browser-runtime/runtime-data/profiles/profile-a",
                "ws://127.0.0.1:9222/devtools/browser/raw-capability token=fake cookie=secret form_body=request request_body=payload",
            ]
        ),
        encoding="utf-8",
    )
    (source / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\nprivate pixels")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "artifact_hygiene_scan.py"),
            "--source",
            str(source),
            "--sanitize-to",
            str(dest),
            "--tier",
            "public-redacted",
            "--strict",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (dest / "PUBLIC-REDACTED-MANIFEST.json").exists()
    assert (dest / "public-summary.json").exists()
    assert (dest / "public-summary.md").exists()
    assert (dest / "public-redaction-scan-report.json").exists()
    assert not (dest / "raw-detector-output.json").exists()
    assert not (dest / "screenshot.png").exists()
    public_text = "\n".join(path.read_text(encoding="utf-8") for path in dest.rglob("*") if path.is_file())
    for forbidden in [
        "8.8.8.8",
        "192.168.1.20",
        "candidate:",
        "typ srflx",
        detector_hash,
        "/home/",
        "runtime-data/profiles",
        "devtools/browser",
        "token=",
        "cookie=",
        "form_body",
        "request_body",
        "MacIntel",
        "America/New_York",
    ]:
        assert forbidden not in public_text
    summary = json.loads((dest / "public-summary.json").read_text())
    assert summary["sensitivity_tier"] == "public_redacted"
    assert summary["public_share_safe"] is True
    assert summary["reports"][0]["measurement_complete"] is True
    scan = json.loads((dest / "public-redaction-scan-report.json").read_text())
    assert scan["public_share_safe"] is True
    assert all(not report["findings"] for report in scan["reports"])


def test_public_redacted_scan_rejects_public_share_hazards(tmp_path: Path):
    hygiene = load_module("artifact_hygiene_public_scan", SCRIPTS / "artifact_hygiene_scan.py")
    public = tmp_path / "public"
    public.mkdir()
    (public / "bad-summary.md").write_text(
        "\n".join(
            [
                "8.8.8.8",
                "candidate:842163049 1 udp 1677729535 8.8.8.8 56144 typ srflx raddr 192.168.1.20 rport 56143",
                "0123456789abcdef0123456789abcdef",
                "/home/fixture/private",
                "runtime-data/profiles/profile-a",
                "profile_id=abc session_id=def",
                "ws://127.0.0.1:9222/devtools/browser/raw-capability token=fake",
                "Authorization: Bearer x cookie=secret form_body=request request_body=payload",
            ]
        ),
        encoding="utf-8",
    )
    (public / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    report = hygiene.scan_path(public, tier="public-redacted")

    kinds = {finding["kind"] for finding in report["findings"]}
    assert {
        "ip_literal",
        "ice_candidate_text",
        "detector_hash",
        "home_path",
        "private_runtime_path",
        "session_or_profile_id",
        "capability_url",
        "public_auth_or_request_marker",
        "public_binary_or_screenshot",
    } <= kinds
