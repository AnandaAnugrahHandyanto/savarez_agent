"""Tests for Feishu Card v2 long-content splitting."""

import json

from gateway.platforms.feishu_card_renderer import build_feishu_card_v2_payloads


def test_long_final_response_splits_into_multiple_cards_without_losing_text():
    text = "\n\n".join(
        f"第 {i:02d} 段：" + ("这是一段用于验证飞书卡片长内容拆分的正文。" * 35)
        for i in range(1, 9)
    )

    payloads = build_feishu_card_v2_payloads(
        text,
        max_markdown_chars=900,
        max_elements_per_card=4,
    )

    assert len(payloads) > 1
    cards = [json.loads(payload) for payload in payloads]
    combined = "\n".join(
        element["content"]
        for card in cards
        for element in card["body"]["elements"]
        if element.get("tag") == "markdown"
    )
    assert "第 01 段" in combined
    assert "第 08 段" in combined
    for card in cards:
        assert len(card["body"]["elements"]) <= 4
        for element in card["body"]["elements"]:
            if element.get("tag") == "markdown":
                assert len(element["content"]) <= 900
    assert cards[0]["header"]["title"]["content"].startswith("Hermes 1/")
    assert cards[-1]["header"]["title"]["content"].startswith(f"Hermes {len(cards)}/")
