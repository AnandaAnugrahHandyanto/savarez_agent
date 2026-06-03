import json
from pathlib import Path

from tools.personal_rag_tool import personal_rag_ingest, personal_rag_list, personal_rag_search


def _payload(result: str) -> dict:
    return json.loads(result)


def test_personal_rag_ingest_search_and_list_text_file(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    doc = tmp_path / "acte-vefa.txt"
    doc.write_text(
        "Le prix de vente est de 239 079 euros. "
        "Le financement est assure par des prets SG et des fonds propres. "
        "La livraison previsionnelle est en juin 2027.",
        encoding="utf-8",
    )

    ingest = _payload(
        personal_rag_ingest(
            str(doc),
            document_type="vefa",
            title="Acte VEFA test",
            chunk_chars=500,
            overlap_chars=50,
        )
    )
    assert ingest["success"] is True
    assert ingest["document_type"] == "vefa"
    assert ingest["chunk_count"] >= 1
    assert Path(ingest["db_path"]).exists()

    listing = _payload(personal_rag_list(document_type="vefa"))
    assert listing["success"] is True
    assert listing["count"] == 1
    assert listing["documents"][0]["title"] == "Acte VEFA test"

    search = _payload(personal_rag_search("fonds propres financement", document_type="vefa", k=3))
    assert search["success"] is True
    assert search["result_count"] >= 1
    assert "fonds propres" in search["passages"][0]["text"].lower()
    assert search["passages"][0]["source_file"] == str(doc.resolve())


def test_personal_rag_search_empty_index_returns_no_passages(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))

    search = _payload(personal_rag_search("apport personnel", document_type="all", k=3))

    assert search["success"] is True
    assert search["result_count"] == 0
    assert search["passages"] == []


def test_personal_rag_ingest_reports_scanned_or_empty_document(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    doc = tmp_path / "empty.txt"
    doc.write_text("   \n\t", encoding="utf-8")

    ingest = _payload(personal_rag_ingest(str(doc), document_type="generic"))

    assert ingest["success"] is False
    assert "No extractable text" in ingest["error"]
