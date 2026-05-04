import json
from pathlib import Path

import pytest

from scripts import hindsight_gateway_benchmark as bench


def test_parse_prometheus_metrics_extracts_process_rss_and_durations():
    metrics = """
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 123456
hindsight_recall_duration_seconds_bucket{le="0.5"} 2
hindsight_recall_duration_seconds_sum 1.25
hindsight_recall_duration_seconds_count 5
operation_duration_seconds_sum{operation="retain"} 0.75
operation_duration_seconds_count{operation="retain"} 3
"""

    parsed = bench.parse_prometheus_metrics(metrics)

    assert parsed["process_resident_memory_bytes"] == 123456.0
    assert parsed["duration_metrics"]["hindsight_recall_duration_seconds"]["sum"] == 1.25
    assert parsed["duration_metrics"]["hindsight_recall_duration_seconds"]["count"] == 5.0
    assert parsed["duration_metrics"]["operation_duration_seconds"]["sum"] == 0.75


def test_parse_smaps_rollup_returns_memory_bytes():
    smaps = """
00400000-00452000 r--p 00000000 08:01 123 /usr/bin/python
Rss:                100 kB
Pss:                 75 kB
Swap:                 3 kB
Private_Clean:       10 kB
"""

    parsed = bench.parse_smaps_rollup(smaps)

    assert parsed == {"rss_bytes": 102400, "pss_bytes": 76800, "swap_bytes": 3072}


@pytest.mark.parametrize(
    ("cmdline", "expected"),
    [
        (["python", "-m", "hindsight.api"], "hindsight"),
        (["/opt/hindsight-server", "--port", "9177"], "hindsight"),
        (["python", "gateway/run.py", "telegram"], "gateway"),
        (["hermes", "gateway", "start"], "gateway"),
        (["python", "worker.py"], None),
        (["python", "scripts/hindsight_gateway_benchmark.py"], None),
        (["bash", "-c", "python scripts/hindsight_gateway_benchmark.py"], None),
    ],
)
def test_categorize_process(cmdline, expected):
    assert bench.categorize_process(cmdline) == expected


def test_build_report_json_shape_with_injected_collectors(tmp_path):
    def fake_now():
        return "2026-05-04T08:30:00+00:00"

    def fake_meminfo():
        return {"MemTotal_bytes": 1000, "MemAvailable_bytes": 600}

    def fake_processes():
        return {
            "hindsight": [
                {
                    "pid": 111,
                    "cmdline": ["python", "-m", "hindsight.api"],
                    "rss_bytes": 10,
                    "pss_bytes": 8,
                    "swap_bytes": 0,
                }
            ],
            "gateway": [],
            "other": [],
        }

    def fake_http(base_url, timeout):
        assert base_url == "http://example.test"
        assert timeout == 1.5
        return {
            "health": {"ok": True, "status": 200, "latency_ms": 10.0, "body": "ok"},
            "version": {"ok": True, "status": 200, "latency_ms": 5.0, "body": '{"version":"x"}'},
            "metrics": {
                "ok": True,
                "status": 200,
                "latency_ms": 2.0,
                "body": "process_resident_memory_bytes 42\nrecall_duration_seconds_sum 0.25\n",
            },
        }

    report = bench.build_report(
        base_url="http://example.test",
        timeout=1.5,
        now_func=fake_now,
        meminfo_func=fake_meminfo,
        processes_func=fake_processes,
        http_func=fake_http,
        recall_func=None,
    )

    assert report["schema_version"] == 1
    assert report["timestamp"] == "2026-05-04T08:30:00+00:00"
    assert report["read_only"] is True
    assert report["hindsight"]["base_url"] == "http://example.test"
    assert report["system_memory"]["MemAvailable_bytes"] == 600
    assert report["processes"]["hindsight"][0]["pid"] == 111
    assert report["hindsight"]["prometheus"]["process_resident_memory_bytes"] == 42.0
    assert report["recall"] == {"enabled": False}

    output = tmp_path / "report.json"
    bench.write_report(report, output)
    assert json.loads(output.read_text())["timestamp"] == report["timestamp"]
