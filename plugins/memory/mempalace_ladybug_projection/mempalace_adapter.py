from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Optional

from .models import Entity, Source, Triple
from .ontology import ADAPTER_NAME, VERSION, hash_json, normalize_entity_id


class MemPalaceKGAdapter:
    """Read-only adapter for MemPalace's knowledge_graph.sqlite3."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def read_entities(self) -> Dict[str, Entity]:
        entities, _ = self._read_entities_with_map()
        return entities

    def _read_entities_with_map(self) -> tuple[Dict[str, Entity], Dict[str, str]]:
        if not self.db_path.exists():
            return {}, {}
        con = sqlite3.connect(self.db_path)
        try:
            rows = con.execute("SELECT id, name, type, properties FROM entities").fetchall()
        except sqlite3.OperationalError:
            return {}, {}
        finally:
            con.close()

        entities: Dict[str, Entity] = {}
        id_map: Dict[str, str] = {}
        for entity_id, name, entity_type, properties in rows:
            raw_id = str(entity_id)
            canonical_id = raw_id if ":" in raw_id else normalize_entity_id(str(entity_type or "unknown"), str(name))
            id_map[raw_id] = canonical_id
            entities[canonical_id] = Entity(
                id=canonical_id,
                name=str(name),
                type=str(entity_type or "unknown"),
                properties=self._loads(properties),
            )
        return entities, id_map

    def read_triples(self) -> list[Triple]:
        if not self.db_path.exists():
            return []
        con = sqlite3.connect(self.db_path)
        try:
            rows = con.execute(
                "SELECT id, subject, predicate, object, valid_from, valid_to, confidence, "
                "source_closet, source_file, source_drawer_id, adapter_name, extracted_at "
                "FROM triples"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()

        entities, id_map = self._read_entities_with_map()
        triples: list[Triple] = []
        for row in rows:
            (
                triple_id,
                subject,
                predicate,
                object_id,
                valid_from,
                valid_to,
                confidence,
                source_closet,
                source_file,
                drawer_id,
                adapter_name,
                extracted_at,
            ) = row
            source = Source(
                drawer_id=str(drawer_id or ""),
                source_file=str(source_file or ""),
                source_closet=str(source_closet or ""),
                adapter_name=str(adapter_name or ADAPTER_NAME),
                adapter_version=VERSION,
                extracted_at=str(extracted_at or ""),
            )
            subject_id = id_map.get(str(subject), str(subject) if ":" in str(subject) else normalize_entity_id("unknown", str(subject)))
            object_id = id_map.get(str(object_id), str(object_id) if ":" in str(object_id) else normalize_entity_id("unknown", str(object_id)))
            triple = Triple(
                triple_id=str(triple_id),
                subject=entities.get(subject_id, Entity(subject_id, subject_id, "unknown")),
                predicate=str(predicate),
                object=entities.get(object_id, Entity(object_id, object_id, "unknown")),
                valid_from=str(valid_from) if valid_from is not None else None,
                valid_to=str(valid_to) if valid_to is not None else None,
                confidence=float(confidence or 1.0),
                source=source,
            )
            triples.append(triple)
        return triples

    def canonical_fingerprint(self, triples: Iterable[Triple]) -> str:
        return hash_json([triple.to_dict() for triple in triples])

    @staticmethod
    def _loads(value: Optional[str]) -> Dict[str, object]:
        if not value:
            return {}
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
