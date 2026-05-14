"""Performance / plan-compliance tests for the achievements plugin.

These tests guard the performance contract described in
``docs/achievements-performance-implementation-plan.md``:

* no ``/overview`` route is exposed
* manifest has no ``slots`` but keeps the Achievements tab
* compiled frontend bundle does not reference the removed slot/overview surface
* ``/achievements`` payload remains backward-compatible and carries
  ``generated_at``/``is_stale``/``scan_meta`` metadata
* pending and in-progress snapshots are reported stale so the UI keeps polling
* the background scan is single-flight
* force rescans never publish partial snapshots
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "dashboard"
MODULE_PATH = PLUGIN_DIR / "plugin_api.py"


def _load_plugin_api():
    spec = importlib.util.spec_from_file_location("plugin_api", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plugin_api = _load_plugin_api()


def _completed_snapshot(generated_at: int, mode: str = "full"):
    return {
        "achievements": [],
        "sessions": [],
        "aggregate": {},
        "scan_meta": {
            "mode": mode,
            "sessions_total": 0,
            "sessions_rescanned": 0,
            "sessions_reused": 0,
        },
        "error": None,
        "unlocked_count": 0,
        "discovered_count": 0,
        "secret_count": 0,
        "total_count": 0,
        "generated_at": generated_at,
    }


class RouteSurfaceTests(unittest.TestCase):
    def test_no_overview_route_registered(self):
        paths = [getattr(route, "path", None) for route in plugin_api.router.routes]
        for path in paths:
            if isinstance(path, str):
                self.assertNotEqual(path, "/overview")
                self.assertFalse(
                    path.endswith("/overview"),
                    f"unexpected /overview route: {path}",
                )

    def test_plugin_api_source_does_not_define_overview_route(self):
        text = MODULE_PATH.read_text()
        for needle in (
            '@router.get("/overview"',
            "@router.get('/overview'",
            '@router.post("/overview"',
        ):
            self.assertNotIn(needle, text)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((PLUGIN_DIR / "manifest.json").read_text())

    def test_manifest_has_no_slots_key(self):
        self.assertNotIn("slots", self.manifest)

    def test_manifest_keeps_achievements_tab(self):
        tab = self.manifest.get("tab")
        self.assertIsInstance(tab, dict)
        self.assertEqual(tab.get("path"), "/achievements")


class DistBundleTests(unittest.TestCase):
    def setUp(self):
        self.text = (PLUGIN_DIR / "dist" / "index.js").read_text()

    def test_dist_has_no_overview_api_call(self):
        for needle in (
            'api("/overview"',
            "api('/overview'",
            '"/overview"',
            "'/overview'",
        ):
            self.assertNotIn(needle, self.text)

    def test_dist_has_no_slot_surface(self):
        for needle in ("registerSlot", "SummarySlot", "sessions:top", "analytics:top"):
            self.assertNotIn(needle, self.text, f"dist bundle still references {needle!r}")


class AchievementsResponseShapeTests(unittest.TestCase):
    def _invoke_achievements(self, snapshot):
        with mock.patch.object(plugin_api, "evaluate_all", return_value=snapshot):
            return asyncio.run(plugin_api.achievements())

    def test_response_carries_compat_keys_and_metadata(self):
        payload = self._invoke_achievements(_completed_snapshot(int(time.time())))
        for key in (
            "achievements",
            "unlocked_count",
            "discovered_count",
            "secret_count",
            "total_count",
            "error",
            "generated_at",
            "is_stale",
            "scan_meta",
        ):
            self.assertIn(key, payload, f"missing key {key!r} in /achievements payload")
        scan_meta = payload["scan_meta"]
        self.assertIn("mode", scan_meta)
        self.assertIn("status", scan_meta)

    def test_fresh_completed_snapshot_is_not_stale(self):
        payload = self._invoke_achievements(_completed_snapshot(int(time.time())))
        self.assertFalse(payload["is_stale"])

    def test_old_completed_snapshot_is_stale(self):
        old_ts = int(time.time()) - (plugin_api.SNAPSHOT_TTL_SECONDS * 3)
        payload = self._invoke_achievements(_completed_snapshot(old_ts))
        self.assertTrue(payload["is_stale"])

    def test_pending_snapshot_is_reported_stale(self):
        snap = _completed_snapshot(int(time.time()), mode="pending")
        payload = self._invoke_achievements(snap)
        self.assertTrue(
            payload["is_stale"],
            "pending snapshots must be reported stale so the UI keeps polling",
        )

    def test_in_progress_snapshot_is_reported_stale(self):
        snap = _completed_snapshot(int(time.time()), mode="in_progress")
        payload = self._invoke_achievements(snap)
        self.assertTrue(
            payload["is_stale"],
            "in_progress snapshots must be reported stale so the UI keeps polling",
        )

    def test_malformed_scan_meta_does_not_crash_staleness_check(self):
        snap = _completed_snapshot(int(time.time()), mode="full")
        snap["scan_meta"] = "corrupt local snapshot metadata"
        payload = self._invoke_achievements(snap)
        self.assertFalse(payload["is_stale"])

    def test_malformed_generated_at_is_reported_stale_without_crashing(self):
        snap = _completed_snapshot(int(time.time()), mode="full")
        snap["generated_at"] = "not-a-timestamp"
        payload = self._invoke_achievements(snap)
        self.assertTrue(payload["is_stale"])
        self.assertEqual(payload["generated_at"], 0)


class BackgroundScanSingleFlightTests(unittest.TestCase):
    def setUp(self):
        self._prev_thread = plugin_api._BACKGROUND_SCAN_THREAD
        self._prev_cache = plugin_api._SNAPSHOT_CACHE
        self._prev_cache_at = plugin_api._SNAPSHOT_CACHE_AT
        plugin_api._BACKGROUND_SCAN_THREAD = None

    def tearDown(self):
        thread = plugin_api._BACKGROUND_SCAN_THREAD
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        plugin_api._BACKGROUND_SCAN_THREAD = self._prev_thread
        plugin_api._SNAPSHOT_CACHE = self._prev_cache
        plugin_api._SNAPSHOT_CACHE_AT = self._prev_cache_at

    def test_concurrent_start_background_scan_spawns_one_worker(self):
        started_counter = []
        stop_event = threading.Event()

        def slow_scan(publish_partial_snapshots=True):
            started_counter.append(threading.current_thread().name)
            stop_event.wait(timeout=2)

        with mock.patch.object(plugin_api, "_run_scan_and_update_cache", side_effect=slow_scan):
            drivers = [
                threading.Thread(target=plugin_api._start_background_scan)
                for _ in range(8)
            ]
            for driver in drivers:
                driver.start()
            for driver in drivers:
                driver.join(timeout=2)
            stop_event.set()
            bg = plugin_api._BACKGROUND_SCAN_THREAD
            if bg is not None:
                bg.join(timeout=3)

        self.assertEqual(
            len(started_counter),
            1,
            f"expected exactly one background scan, got {len(started_counter)}",
        )

    def test_evaluate_all_no_cache_spawns_one_background_scan(self):
        plugin_api._SNAPSHOT_CACHE = None
        plugin_api._SNAPSHOT_CACHE_AT = 0
        starts = []
        stop_event = threading.Event()

        def slow_scan(publish_partial_snapshots=True):
            starts.append(time.time())
            stop_event.wait(timeout=2)

        with mock.patch.object(plugin_api, "load_snapshot", return_value=None), \
                mock.patch.object(plugin_api, "_run_scan_and_update_cache", side_effect=slow_scan):
            drivers = [threading.Thread(target=plugin_api.evaluate_all) for _ in range(5)]
            for d in drivers:
                d.start()
            for d in drivers:
                d.join(timeout=2)
            stop_event.set()
            bg = plugin_api._BACKGROUND_SCAN_THREAD
            if bg is not None:
                bg.join(timeout=3)

        self.assertEqual(
            len(starts),
            1,
            f"expected one background scan from concurrent evaluate_all calls, got {len(starts)}",
        )


class ForceRescanTests(unittest.TestCase):
    def setUp(self):
        self._prev_cache = plugin_api._SNAPSHOT_CACHE
        self._prev_cache_at = plugin_api._SNAPSHOT_CACHE_AT
        plugin_api._SNAPSHOT_CACHE = None
        plugin_api._SNAPSHOT_CACHE_AT = 0

    def tearDown(self):
        plugin_api._SNAPSHOT_CACHE = self._prev_cache
        plugin_api._SNAPSHOT_CACHE_AT = self._prev_cache_at

    def test_force_rescan_disables_partial_publishing(self):
        captured = {}

        def fake_run(publish_partial_snapshots=True):
            captured["publish_partial_snapshots"] = publish_partial_snapshots
            now = int(time.time())
            plugin_api._SNAPSHOT_CACHE = _completed_snapshot(now)
            plugin_api._SNAPSHOT_CACHE_AT = now

        with mock.patch.object(plugin_api, "_run_scan_and_update_cache", side_effect=fake_run):
            result = plugin_api.evaluate_all(force=True)

        self.assertIs(
            captured.get("publish_partial_snapshots"),
            False,
            "force rescan must call _run_scan_and_update_cache(publish_partial_snapshots=False)",
        )
        self.assertEqual(result["scan_meta"]["mode"], "full")
        self.assertIsNone(result["error"])

    def test_force_rescan_compute_does_not_receive_progress_callback(self):
        seen = {}

        def fake_compute(progress_callback=None, progress_every=250):
            seen["progress_callback"] = progress_callback
            return _completed_snapshot(int(time.time()))

        with mock.patch.object(plugin_api, "compute_all", side_effect=fake_compute), \
                mock.patch.object(plugin_api, "save_snapshot", return_value=None):
            result = plugin_api.evaluate_all(force=True)

        self.assertIsNone(
            seen.get("progress_callback"),
            "force rescan must not pass a partial-publishing callback to compute_all",
        )
        self.assertEqual(result["scan_meta"]["mode"], "full")


class PersistedSnapshotCorruptionTests(unittest.TestCase):
    def setUp(self):
        self._prev_cache = plugin_api._SNAPSHOT_CACHE
        self._prev_cache_at = plugin_api._SNAPSHOT_CACHE_AT
        plugin_api._SNAPSHOT_CACHE = None
        plugin_api._SNAPSHOT_CACHE_AT = 0

    def tearDown(self):
        plugin_api._SNAPSHOT_CACHE = self._prev_cache
        plugin_api._SNAPSHOT_CACHE_AT = self._prev_cache_at

    def test_malformed_persisted_generated_at_triggers_refresh_without_crashing(self):
        persisted = _completed_snapshot(int(time.time()), mode="full")
        persisted["generated_at"] = "not-a-timestamp"
        with mock.patch.object(plugin_api, "load_snapshot", return_value=persisted), \
                mock.patch.object(plugin_api, "_start_background_scan") as start_scan:
            result = plugin_api.evaluate_all()

        self.assertIs(result, persisted)
        start_scan.assert_called_once()
        self.assertEqual(plugin_api._SNAPSHOT_CACHE_AT, 0)

    def test_scan_status_tolerates_malformed_cached_generated_at(self):
        plugin_api._SNAPSHOT_CACHE = _completed_snapshot(int(time.time()), mode="full")
        plugin_api._SNAPSHOT_CACHE["generated_at"] = "not-a-timestamp"

        status = plugin_api._scan_status_payload()

        self.assertIsNone(status["snapshot_generated_at"])
        self.assertIsNone(status["snapshot_age_seconds"])
        self.assertTrue(status["snapshot_stale"])


if __name__ == "__main__":
    unittest.main()
