from education.normalize import NormalizedDocument, normalize_mineru_markdown


SAMPLE_MARKDOWN = """# 二次函数练习
[PAGE:1]
已知 $a^2+b^2=c^2$。

$$E=mc^2$$

| 列 | 值 |
| --- | --- |
| A | 1 |

![figure](images/q1.png)
"""


def test_normalize_mineru_markdown_preserves_formula_content(tmp_path):
    result = normalize_mineru_markdown(SAMPLE_MARKDOWN, document_id="doc001", output_dir=tmp_path)

    assert "$a^2+b^2=c^2$" in result.markdown
    assert "$$E=mc^2$$" in result.markdown


def test_normalize_mineru_markdown_assigns_stable_block_ids(tmp_path):
    result = normalize_mineru_markdown(SAMPLE_MARKDOWN, document_id="doc001", output_dir=tmp_path)

    assert [block.block_id for block in result.blocks] == [
        "blk_doc001_0001",
        "blk_doc001_0002",
        "blk_doc001_0003",
        "blk_doc001_0004",
        "blk_doc001_0005",
    ]


def test_normalize_mineru_markdown_tracks_page_metadata(tmp_path):
    result = normalize_mineru_markdown(SAMPLE_MARKDOWN, document_id="doc001", output_dir=tmp_path)

    assert all(block.page_start == 1 for block in result.blocks)
    assert all(block.page_end == 1 for block in result.blocks)


def test_normalize_mineru_markdown_writes_normalized_artifact(tmp_path):
    result = normalize_mineru_markdown(SAMPLE_MARKDOWN, document_id="doc001", output_dir=tmp_path)

    assert result.artifact_path.exists()
    assert result.artifact_path.read_text(encoding="utf-8") == result.markdown
    assert result.artifact_path.name == "normalized.md"
