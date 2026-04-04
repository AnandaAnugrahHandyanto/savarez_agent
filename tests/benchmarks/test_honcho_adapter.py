from benchmarks.backends.honcho_adapter import HonchoBenchmarkAdapter


class FakeSession:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content, **kwargs):
        self.messages.append({"role": role, "content": content})


class FakeManager:
    def __init__(self):
        self.session = FakeSession()
        self.saved = 0
        self.flushed = 0
        self.deleted = 0

    def get_or_create(self, key):
        return self.session

    def save(self, session):
        self.saved += 1

    def flush_all(self):
        self.flushed += 1

    def search_context(self, session_key, query, max_tokens=800):
        joined = "\n".join(m["content"] for m in self.session.messages)
        if "region" in query.lower() and "us-east-1" in joined:
            return "production region is us-east-1"
        return ""

    def dialectic_query(self, session_key, query, peer="user"):
        return ""

    def delete(self, key):
        self.deleted += 1
        self.session = FakeSession()
        return True


def test_honcho_adapter_store_and_recall_with_fake_manager():
    backend = HonchoBenchmarkAdapter(manager=FakeManager())
    backend.reset()
    backend.store("production region is us-east-1")
    results = backend.recall("What region are we using?", top_k=3)
    assert any("us-east-1" in r for r in results)


def test_honcho_adapter_requires_configuration_without_manager():
    backend = HonchoBenchmarkAdapter(api_key=None, base_url=None)
    try:
        backend.store("test")
    except RuntimeError as e:
        assert "HONCHO_API_KEY" in str(e) or "HONCHO_BASE_URL" in str(e)
    else:
        raise AssertionError("Expected RuntimeError when Honcho is not configured")
