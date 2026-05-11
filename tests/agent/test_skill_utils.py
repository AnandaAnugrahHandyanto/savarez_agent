"""Tests for agent/skill_utils.py — extract_skill_conditions metadata handling."""

from agent.skill_utils import extract_skill_conditions


def test_metadata_as_dict_with_hermes():
    """Normal case: metadata is a dict containing hermes keys."""
    frontmatter = {
        "metadata": {
            "hermes": {
                "fallback_for_toolsets": ["toolset_a"],
                "requires_toolsets": ["toolset_b"],
                "fallback_for_tools": ["tool_x"],
                "requires_tools": ["tool_y"],
            }
        }
    }
    result = extract_skill_conditions(frontmatter)
    assert result["fallback_for_toolsets"] == ["toolset_a"]
    assert result["requires_toolsets"] == ["toolset_b"]
    assert result["fallback_for_tools"] == ["tool_x"]
    assert result["requires_tools"] == ["tool_y"]


def test_metadata_as_string_does_not_crash():
    """Bug case: metadata is a non-dict truthy value (e.g. a YAML string)."""
    frontmatter = {"metadata": "some text"}
    result = extract_skill_conditions(frontmatter)
    assert result == {
        "fallback_for_toolsets": [],
        "requires_toolsets": [],
        "fallback_for_tools": [],
        "requires_tools": [],
    }


def test_metadata_as_none():
    """metadata key is present but set to null/None."""
    frontmatter = {"metadata": None}
    result = extract_skill_conditions(frontmatter)
    assert result == {
        "fallback_for_toolsets": [],
        "requires_toolsets": [],
        "fallback_for_tools": [],
        "requires_tools": [],
    }


def test_metadata_missing_entirely():
    """metadata key is absent from frontmatter."""
    frontmatter = {"name": "my-skill", "description": "Does stuff."}
    result = extract_skill_conditions(frontmatter)
    assert result == {
        "fallback_for_toolsets": [],
        "requires_toolsets": [],
        "fallback_for_tools": [],
        "requires_tools": [],
    }


# ── Locale-aware description tests ────────────────────────────────────────

from agent.skill_utils import extract_skill_description


def test_description_en_fallback():
    """language='en' always returns 'description', ignoring description_zh."""
    fm = {"description": "Hello world", "description_zh": "你好世界"}
    assert extract_skill_description(fm, language="en") == "Hello world"


def test_description_zh_selected():
    """language='zh' prefers description_zh when present."""
    fm = {"description": "Hello world", "description_zh": "你好世界"}
    assert extract_skill_description(fm, language="zh") == "你好世界"


def test_description_zh_fallback_to_en():
    """language='zh' falls back to description when description_zh absent."""
    fm = {"description": "Hello world"}
    assert extract_skill_description(fm, language="zh") == "Hello world"


def test_description_de_selected():
    """language='de' prefers description_de when present."""
    fm = {"description": "Hello", "description_de": "Hallo"}
    assert extract_skill_description(fm, language="de") == "Hallo"


def test_description_zh_truncated():
    """Chinese description over 60 chars is truncated with ellipsis."""
    long_zh = "这是一个" + "很长" * 30 + "的描述文本"
    assert len(long_zh) > 60, f"test string must be >60 chars, got {len(long_zh)}"
    fm = {"description_zh": long_zh}
    result = extract_skill_description(fm, language="zh")
    assert result.endswith("...")
    assert len(result) <= 60


def test_description_default_language_en():
    """Default language=en ignores description_zh."""
    fm = {"description": "Hello", "description_zh": "你好"}
    assert extract_skill_description(fm) == "Hello"
