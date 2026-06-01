"""Tests for the interactive `hermes plugins` composite menu model."""

from hermes_cli import plugins_cmd


def test_composite_navigation_items_preserve_original_order():
    assert plugins_cmd._composite_navigation_items(n_plugins=2, n_categories=2) == [
        ("plugin", 0),
        ("plugin", 1),
        ("category", 0),
        ("category", 1),
    ]


def test_build_composite_rows_preserves_general_before_provider_plugins():
    categories = [
        ("Memory Provider", "built-in", lambda: False),
        ("Context Engine", "compressor", lambda: False),
    ]

    rows = plugins_cmd._build_composite_rows(
        plugin_labels=["plugin-a", "plugin-b"],
        categories=categories,
    )

    labels = [row.get("label", "") for row in rows]
    assert labels.index("General Plugins") < labels.index("Provider Plugins")

    navigable = [row for row in rows if row.get("nav")]
    assert navigable[0]["kind"] == "plugin"
    assert navigable[0]["plugin_index"] == 0
    assert navigable[2]["kind"] == "category"
    assert navigable[2]["category_index"] == 0
    assert navigable[2]["label"].startswith("Memory Provider")
