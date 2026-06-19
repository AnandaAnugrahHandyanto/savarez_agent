from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from statistics import mean

from .aegis import AegisPolicyGate, PolicyConfig
from .mempalace_adapter import MemPalaceKGAdapter
from .projection import DroidProjectionWorker, LadybugSQLiteStore


def _count_rows(db: Path, table: str) -> int:
    con = sqlite3.connect(db)
    try:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    finally:
        con.close()


def run_benchmark(mempalace_home: str | Path, output_dir: str | Path, iterations: int = 25) -> dict:
    mempalace_home = Path(mempalace_home)
    output_dir = Path(output_dir)
    source_db = mempalace_home / "knowledge_graph.sqlite3"
    entity_count = _count_rows(source_db, "entities") if source_db.exists() else 0
    fact_count = _count_rows(source_db, "triples") if source_db.exists() else 0

    start = time.perf_counter()
    manifest = DroidProjectionWorker(output_dir).build(source_db)
    rebuild_seconds = time.perf_counter() - start

    store = LadybugSQLiteStore(output_dir / "active" / "ladybug.sqlite3")
    api = MCPReadAPICompat(store, AegisPolicyGate(PolicyConfig()))
    latencies = []
    for _ in range(iterations):
        start = time.perf_counter()
        api.handle_tool_call("kg_subgraph", {"entity_id": "person:warren-l", "predicates": ["leads"], "max_depth": 2, "max_nodes": 25, "max_edges": 50}, str(output_dir / "active"))
        latencies.append((time.perf_counter() - start) * 1000)

    return {
        "benchmark": "mempalace-ladybug-projection-v0.2.0",
        "entity_count": entity_count,
        "fact_count": fact_count,
        "rebuild_seconds": round(rebuild_seconds, 6),
        "query_count": iterations,
        "query_latency_ms_mean": round(mean(latencies), 6) if latencies else 0,
        "query_latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0, 6),
        "manifest": manifest,
    }


class MCPReadAPICompat:
    def __init__(self, store: LadybugSQLiteStore, gate: AegisPolicyGate):
        self.store = store
        self.gate = gate

    def handle_tool_call(self, name: str, arguments: dict, active_projection: str) -> str:
        con = self.store._connect()
        try:
            nodes = {row[0]: {"id": row[0], "name": row[1], "type": row[2], "properties": json.loads(row[3])} for row in con.execute("SELECT id, name, type, properties FROM nodes").fetchall()}
            edges = [{"id": row[0], "subject": row[1], "predicate": row[2], "object": row[3], "properties": json.loads(row[4])} for row in con.execute("SELECT id, subject, predicate, object, properties FROM edges").fetchall()]
        finally:
            con.close()
        decision = self.gate.evaluate(arguments, {"nodes": nodes, "edges": edges})
        return json.dumps(decision.filtered_graph, sort_keys=True)


if __name__ == "__main__":
    print(json.dumps(run_benchmark(Path.home() / ".mempalace", Path.home() / ".hermes" / "benchmarks" / "mempalace-ladybug-projection"), indent=2, sort_keys=True))
