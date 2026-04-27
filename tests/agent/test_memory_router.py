"""Tests for lightweight memory routing and active context capsules."""

from agent.memory_router import (
    ActiveContextCapsule,
    ActiveContextCapsuleCache,
    MemoryRouter,
)


def test_router_detects_nutrition_first_turn():
    route = MemoryRouter().classify("На завтрак был съеден омлет из 2 яиц")

    assert route.action == "domain_capsule"
    assert route.topic == "nutrition"
    assert "nutrition" in route.reason


def test_router_detects_standalone_ate_word():
    route = MemoryRouter().classify("я ел омлет")

    assert route.action == "domain_capsule"
    assert route.topic == "nutrition"


def test_router_does_not_match_ate_inside_other_words():
    router = MemoryRouter()

    for message in ("я хотел спросить про OpenClaw", "я видел ошибку", "смотрел логи"):
        route = router.classify(message)
        assert route.action == "skip", message


def test_router_does_not_match_nutrition_stems_inside_other_words():
    router = MemoryRouter()

    for message in ("победа будет за нами", "мы победим", "белокурый персонаж"):
        route = router.classify(message)
        assert route.action == "skip", message


def test_router_reuses_active_nutrition_topic():
    route = MemoryRouter().classify("а йогурт можно?", active_topic="nutrition")

    assert route.action == "reuse_active_capsule"
    assert route.topic == "nutrition"


def test_router_explicit_past_reference_overrides_active_topic_reuse():
    route = MemoryRouter().classify(
        "помнишь, какой йогурт мы обсуждали?",
        active_topic="nutrition",
    )

    assert route.action == "hindsight_now"
    assert route.topic == "nutrition"


def test_router_does_not_match_past_reference_inside_other_words_or_plain_narrative():
    router = MemoryRouter()

    for message in (
        "если вспомнишь потом, напиши",
        "мы обсуждали это с командой вчера",
        "please remove the word previously from the docs",
    ):
        route = router.classify(message)
        assert route.action == "skip", message


def test_router_detects_explicit_past_reference():
    route = MemoryRouter().classify("помнишь, что мы обсуждали по OpenClaw?")

    assert route.action == "hindsight_now"
    assert route.reason == "explicit past-reference"


def test_router_skips_empty_message():
    route = MemoryRouter().classify("   ")

    assert route.action == "skip"


def test_active_capsule_cache_reuses_until_ttl():
    cache = ActiveContextCapsuleCache(default_ttl_turns=2)
    cache.set(
        ActiveContextCapsule(
            topic="nutrition",
            text="User eats two meals per day.",
            created_turn=1,
            last_used_turn=1,
            ttl_turns=2,
        )
    )

    assert cache.active_topic(current_turn=2) == "nutrition"
    assert cache.get("nutrition", current_turn=2) == "User eats two meals per day."
    assert cache.get("nutrition", current_turn=4) == ""


def test_active_capsule_cache_does_not_reuse_wrong_topic():
    cache = ActiveContextCapsuleCache(default_ttl_turns=5)
    cache.set(ActiveContextCapsule(topic="nutrition", text="Nutrition context", created_turn=1))

    assert cache.get("bro-pm", current_turn=2) == ""
