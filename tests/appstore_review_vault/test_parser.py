from appstore_review_vault.parser import parse_reviews_feed


def sample_payload():
    return {
        "feed": {
            "entry": [
                {
                    "author": {"name": {"label": "A User"}, "uri": {"label": "https://example.com/u"}},
                    "updated": {"label": "2026-06-01T12:00:00-07:00"},
                    "im:rating": {"label": "5"},
                    "im:version": {"label": "1.2.3"},
                    "id": {"label": "12345"},
                    "title": {"label": "Great"},
                    "content": {"label": "Works well"},
                    "link": {"attributes": {"href": "https://apps.apple.com/review/12345"}},
                    "im:voteSum": {"label": "3"},
                    "im:voteCount": {"label": "4"},
                }
            ]
        }
    }


def test_parse_reviews_feed_normalizes_entries():
    reviews = parse_reviews_feed(sample_payload())

    assert reviews == [
        {
            "review_id": "12345",
            "rating": 5,
            "version": "1.2.3",
            "title": "Great",
            "body": "Works well",
            "author_name": "A User",
            "author_url": "https://example.com/u",
            "review_url": "https://apps.apple.com/review/12345",
            "updated_at_apple": "2026-06-01T12:00:00-07:00",
            "vote_sum": 3,
            "vote_count": 4,
        }
    ]


def test_parse_reviews_feed_handles_missing_optional_fields():
    payload = sample_payload()
    entry = payload["feed"]["entry"][0]
    del entry["author"]["uri"]
    del entry["link"]
    del entry["im:voteSum"]
    del entry["im:voteCount"]

    review = parse_reviews_feed(payload)[0]

    assert review["author_url"] is None
    assert review["review_url"] is None
    assert review["vote_sum"] is None
    assert review["vote_count"] is None


def test_parse_reviews_feed_empty_feed_returns_empty_list():
    assert parse_reviews_feed({"feed": {}}) == []
