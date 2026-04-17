from education.paths import (
    education_root,
    question_bank_db_path,
    raw_artifacts_root,
    mineru_artifacts_root,
    normalized_artifacts_root,
    wiki_artifacts_root,
)


def test_education_paths_resolve_under_hermes_home(tmp_path, monkeypatch):
    fake_home = tmp_path / "custom_hermes_home"
    fake_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(fake_home))

    expected_root = fake_home / "education"

    assert education_root() == expected_root
    assert question_bank_db_path() == expected_root / "question_bank.db"
    assert raw_artifacts_root() == expected_root / "artifacts" / "raw"
    assert mineru_artifacts_root() == expected_root / "artifacts" / "mineru"
    assert normalized_artifacts_root() == expected_root / "artifacts" / "normalized"
    assert wiki_artifacts_root() == expected_root / "artifacts" / "wiki"
