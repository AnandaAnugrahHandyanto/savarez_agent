"""Deterministic MVP agent pipeline for Marketing Agent Factory.

The MVP intentionally avoids real public posting and avoids LLM/API calls. The
interfaces and records carry model-routing metadata so Claude CLI/OAuth, local
models, OpenRouter, OpenAI, Anthropic, and posting APIs can be introduced behind
approval and dry-run gates later.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from plugins.marketing_factory.store import MarketingFactoryStore, utc_now


PUPULAR_PROFILE: Dict[str, Any] = {
    "slug": "pupular",
    "name": "Pupular",
    "positioning": "A cute, modern adopt-a-pet app that helps people discover real adoptable pets.",
    "icp": "Pet lovers, adopters, rescue supporters, and families looking for a new companion.",
    "tone": "Cute, warm, optimistic, brand-safe, playful but never flippant about adoption.",
    "cta": "Download Pupular and meet adoptable pets near you.",
    "links": ["https://apps.apple.com/us/app/pupular-adopt-a-pet/id6761799693"],
    "channels": ["x", "instagram", "tiktok", "app_store"],
    "content_pillars": ["real adoptable pets", "adoption joy", "shelter support", "cute animal moments"],
    "claims": ["Helps people discover adoptable pets", "Available on the App Store"],
    "forbidden_claims": ["Guaranteed adoption", "medical or behavioral guarantees", "shelter affiliation unless verified"],
    "assets": ["real pet photos", "app screenshots", "short cute captions"],
    "competitors": ["Petfinder", "Adopt a Pet"],
    "current_campaigns": ["Four cute posts per day cadence"],
}

SETVENUE_PROFILE: Dict[str, Any] = {
    "slug": "setvenue",
    "name": "SetVenue",
    "positioning": "A marketplace for booking unique homes and spaces for productions, events, and creative work.",
    "icp": "Producers, photographers, creators, event planners, and hosts with bookable spaces.",
    "tone": "Trustworthy, practical, premium, clear, founder-led, conversion-focused.",
    "cta": "List your space or book a unique venue on SetVenue.",
    "links": ["https://setvenue.com"],
    "channels": ["linkedin", "x", "blog", "email"],
    "content_pillars": ["unique venues", "host earnings", "production logistics", "trust and booking flow"],
    "claims": ["Hosts can submit homes", "Bookings are finalized after host approval"],
    "forbidden_claims": ["Guaranteed income", "instant booking when host approval is required", "unverified customer counts"],
    "assets": ["venue screenshots", "listing examples", "booking flow visuals"],
    "competitors": ["Peerspace", "Giggster", "Airbnb for events"],
    "current_campaigns": ["Host acquisition and booker trust"],
}

SAMPLE_PROFILES = {"pupular": PUPULAR_PROFILE, "setvenue": SETVENUE_PROFILE}


class BrandBrainAgent:
    def __init__(self, store: MarketingFactoryStore):
        self.store = store

    def seed_samples(self) -> List[Dict[str, Any]]:
        return [self.store.upsert_app(profile) for profile in SAMPLE_PROFILES.values()]


class ResearchAgent:
    def research(self, app: Dict[str, Any]) -> Dict[str, Any]:
        pillars = app.get("content_pillars") or []
        channels = app.get("channels") or []
        return {
            "generated_at": utc_now(),
            "agent": "research",
            "model_route": "cheap",
            "trends": [f"{pillar} conversation hooks" for pillar in pillars[:3]],
            "pain_points": _pain_points(app["slug"]),
            "channel_opportunities": {channel: _channel_opportunity(app["slug"], channel) for channel in channels},
            "competitors": app.get("competitors", []),
        }


class StrategyAgent:
    def plan_campaign(self, app: Dict[str, Any], research: Dict[str, Any], days: int = 7) -> Dict[str, Any]:
        objective = "app adoption and brand awareness" if app["slug"] == "pupular" else "host/booker acquisition and trust"
        plan = []
        base = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)
        channels = app.get("channels") or ["x"]
        for idx in range(days):
            channel = channels[idx % len(channels)]
            pillar = (app.get("content_pillars") or ["brand story"])[idx % len(app.get("content_pillars") or ["brand story"])]
            plan.append({
                "day": idx + 1,
                "date": (base + timedelta(days=idx)).date().isoformat(),
                "channel": channel,
                "pillar": pillar,
                "angle": _angle_for(app["slug"], pillar),
                "scheduled_for": (base + timedelta(days=idx)).isoformat(),
            })
        return {
            "name": f"{app['name']} MVP Dry-Run Campaign",
            "objective": objective,
            "channels": channels,
            "research_summary": research,
            "plan": plan,
            "model_route": "premium",
        }


class CopyAgent:
    def draft_for_item(self, app: Dict[str, Any], campaign_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
        body = _draft_body(app, item)
        return {
            "campaign_id": campaign_id,
            "channel": item["channel"],
            "content_type": _content_type(item["channel"]),
            "body": body,
            "cta": app.get("cta"),
            "assets": _asset_concepts(app, item),
            "model_route": "mid" if item["channel"] in {"blog", "email", "linkedin"} else "cheap",
        }


class CreativeAgent:
    def add_concepts(self, app: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
        draft = dict(draft)
        draft["creative_concepts"] = _asset_concepts(app, {"pillar": draft.get("content_type", "post"), "channel": draft["channel"]})
        return draft


class ReviewSafetyAgent:
    def review(self, app: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
        body_lower = draft["body"].lower()
        forbidden_hits = [claim for claim in app.get("forbidden_claims", []) if claim.lower() in body_lower]
        channel_ok = _within_channel_constraints(draft["channel"], draft["body"])
        useful = len(draft["body"].strip()) >= 40
        passed = not forbidden_hits and channel_ok and useful
        return {
            "agent": "review_safety",
            "model_route": "premium",
            "passed": passed,
            "checks": {
                "brand_fit": True,
                "forbidden_claims": forbidden_hits,
                "channel_constraints": channel_ok,
                "spam_risk": "low",
                "duplicate_risk": "low",
                "hallucinated_claims_risk": "low" if not forbidden_hits else "medium",
                "useful": useful,
            },
            "recommendation": "needs_human_approval" if passed else "reject_or_rewrite",
        }


class SchedulerAgent:
    def schedule_approved(self, store: MarketingFactoryStore, app_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        scheduled = []
        drafts = store.list_drafts(app_slug=app_slug, status="approved")
        base = datetime.now(timezone.utc).replace(hour=15, minute=0, second=0, microsecond=0)
        for idx, draft in enumerate(drafts):
            scheduled_for = draft.get("scheduled_for") or (base + timedelta(days=idx)).isoformat()
            scheduled.append(store.schedule_draft(draft["id"], scheduled_for))
        return scheduled


class PublisherAgent:
    def dry_run_publish_scheduled(self, store: MarketingFactoryStore, app_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        events = []
        for schedule in store.list_schedules(app_slug=app_slug):
            draft = store.get_draft(schedule["draft_id"], app_slug=schedule["app_slug"])
            if draft["status"] == "scheduled":
                events.append(store.dry_run_publish(draft["id"]))
        return events


class AnalyticsAgent:
    def feed_learning(self, store: MarketingFactoryStore, app_slug: str, summary: str) -> Dict[str, Any]:
        return store.record_analytics(app_slug, {"source": "dry_run", "summary": summary, "learning": summary})


class MarketingFactoryPipeline:
    def __init__(self, store: Optional[MarketingFactoryStore] = None):
        self.store = store or MarketingFactoryStore()
        self.brand = BrandBrainAgent(self.store)
        self.research = ResearchAgent()
        self.strategy = StrategyAgent()
        self.copy = CopyAgent()
        self.creative = CreativeAgent()
        self.review = ReviewSafetyAgent()
        self.scheduler = SchedulerAgent()
        self.publisher = PublisherAgent()
        self.analytics = AnalyticsAgent()

    def initialize_samples(self) -> Dict[str, Any]:
        self.store.initialize()
        apps = self.brand.seed_samples()
        return {"apps": apps, "summary": self.store.summary()}

    def generate_campaign(self, app_slug: str, days: int = 7, auto_approve: bool = False) -> Dict[str, Any]:
        app = self.store.require_app(app_slug)
        research = self.research.research(app)
        campaign_plan = self.strategy.plan_campaign(app, research, days=days)
        campaign = self.store.create_campaign(app["slug"], campaign_plan)
        drafts = []
        for item in campaign["plan"]:
            raw_draft = self.copy.draft_for_item(app, campaign["id"], item)
            raw_draft["scheduled_for"] = item["scheduled_for"]
            enriched = self.creative.add_concepts(app, raw_draft)
            safety = self.review.review(app, enriched)
            enriched["safety"] = safety
            enriched["status"] = "needs_review" if safety["passed"] else "rejected"
            draft = self.store.create_draft(app["slug"], enriched)
            if auto_approve and safety["passed"]:
                self.store.set_approval(draft["id"], "approved", reviewer="auto-test", reason="auto approval for dry-run verification only")
                draft = self.store.get_draft(draft["id"])
            drafts.append(draft)
        self.store.audit("campaign.generated", app["slug"], {"campaign_id": campaign["id"], "draft_count": len(drafts), "auto_approve": auto_approve})
        return {"app": app, "campaign": campaign, "drafts": drafts}

    def approve_all_for_app(self, app_slug: str, reviewer: str = "human") -> List[Dict[str, Any]]:
        approvals = []
        for draft in self.store.list_drafts(app_slug=app_slug, status="needs_review"):
            if draft.get("safety", {}).get("passed"):
                approvals.append(self.store.set_approval(draft["id"], "approved", reviewer=reviewer, reason="approved for dry-run scheduling"))
        return approvals

    def run_full_dry_run(self, app_slug: str, days: int = 7, reviewer: str = "human") -> Dict[str, Any]:
        generated = self.generate_campaign(app_slug, days=days, auto_approve=False)
        approvals = self.approve_all_for_app(app_slug, reviewer=reviewer)
        schedules = self.scheduler.schedule_approved(self.store, app_slug=app_slug)
        publish_events = self.publisher.dry_run_publish_scheduled(self.store, app_slug=app_slug)
        learning = self.analytics.feed_learning(
            self.store,
            app_slug,
            f"Dry-run campaign generated {len(generated['drafts'])} drafts, scheduled {len(schedules)}, and produced {len(publish_events)} dry-run publish events.",
        )
        return {"generated": generated, "approvals": approvals, "schedules": schedules, "publish_events": publish_events, "analytics": learning}


def _pain_points(slug: str) -> List[str]:
    if slug == "pupular":
        return ["Finding adoptable pets feels fragmented", "People want cute, trustworthy pet discovery", "Shelters need more attention for real pets"]
    if slug == "setvenue":
        return ["Producers need unique spaces without endless back-and-forth", "Hosts need trust and clear booking expectations", "Bookers want to know approval and payment timing"]
    return ["Audience needs clearer education", "Brand needs consistent channel-native content"]


def _channel_opportunity(slug: str, channel: str) -> str:
    if slug == "pupular":
        return f"Use {channel} for cute, real-pet discovery hooks with App Store CTA."
    if slug == "setvenue":
        return f"Use {channel} for trust-building venue education and host/booker conversion."
    return f"Use {channel} for brand-safe useful content."


def _angle_for(slug: str, pillar: str) -> str:
    if slug == "pupular":
        return f"Make {pillar} feel immediate, cute, and adoption-positive."
    if slug == "setvenue":
        return f"Explain {pillar} with practical trust and booking clarity."
    return f"Turn {pillar} into a clear audience benefit."


def _content_type(channel: str) -> str:
    return {"blog": "seo_outline", "email": "email", "linkedin": "linkedin_post", "x": "short_social", "instagram": "visual_caption", "tiktok": "short_script", "app_store": "app_store_copy"}.get(channel, "post")


def _draft_body(app: Dict[str, Any], item: Dict[str, Any]) -> str:
    link = app.get("links", [""])[0]
    if app["slug"] == "pupular":
        return (
            f"Tiny paws, huge main-character energy. Today’s {item['pillar']} reminder: adoptable pets are out there waiting to be discovered. "
            f"Open Pupular, meet real pets, and maybe find your next best friend. {link}"
        )
    if app["slug"] == "setvenue":
        return (
            f"Great shoots and events start with the right space. SetVenue helps teams discover unique homes and venues while keeping booking expectations clear: "
            f"requests go to hosts, and payment is finalized after host approval. {link}"
        )
    return f"{app['name']} helps {app.get('icp', 'its audience')} with {item['pillar']}. {app.get('cta', '')} {link}".strip()


def _asset_concepts(app: Dict[str, Any], item: Dict[str, Any]) -> List[str]:
    if app["slug"] == "pupular":
        return ["Real adoptable pet photo with soft rounded caption card", "Short vertical clip prompt: happy pet close-up + App Store CTA"]
    if app["slug"] == "setvenue":
        return ["Premium venue screenshot carousel: space, use case, booking clarity", "Short explainer graphic: request → host approval → finalized booking"]
    return [f"Brand-safe visual concept for {item.get('pillar', 'campaign')}"]


def _within_channel_constraints(channel: str, body: str) -> bool:
    if channel == "x":
        return len(body) <= 280
    if channel in {"linkedin", "email", "blog"}:
        return len(body) <= 5000
    return len(body) <= 2200
