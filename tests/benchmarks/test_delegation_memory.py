from benchmarks.judge import HeuristicJudge
from benchmarks.runner import run_delegation_memory


class DelegationBackend:
    STOPWORDS = {"what", "did", "the", "a", "an", "we", "our", "to", "for", "do"}

    def __init__(self):
        self.memories = []

    def reset(self):
        self.memories = []

    def store(self, content: str, category: str = "factual", scope: str = "global", importance: float = 0.5):
        self.memories.append(content)

    def recall(self, query: str, top_k: int = 10, scope=None):
        tokens = [t for t in query.lower().replace("?", "").split() if t not in self.STOPWORDS]
        scored = []
        for memory in self.memories:
            score = 0
            lower = memory.lower()
            for token in tokens:
                if token in lower:
                    score += 1
            scored.append((score, memory))
        scored.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
        return [memory for score, memory in scored[:top_k] if score > 0]


def test_delegation_memory_passes_when_result_contains_answer():
    backend = DelegationBackend()
    judge = HeuristicJudge(model="heuristic")
    scenarios = [
        {
            "id": "dm_test_01",
            "delegation_task": "Investigate deployment region.",
            "delegation_result": "Recommendation: deploy production in us-east-1.",
            "query": "What region did the delegated deployment investigation recommend?",
            "gold_answer": "us-east-1",
            "difficulty": "easy",
        }
    ]

    result = run_delegation_memory(backend, scenarios, judge)
    assert result.correct == 1
    assert result.score == 1.0


def test_delegation_memory_fails_when_result_does_not_contain_answer():
    backend = DelegationBackend()
    judge = HeuristicJudge(model="heuristic")
    scenarios = [
        {
            "id": "dm_test_02",
            "delegation_task": "Investigate deployment region.",
            "delegation_result": "Recommendation: the team discussed several possible regions.",
            "query": "What region did the delegated deployment investigation recommend?",
            "gold_answer": "us-east-1",
            "difficulty": "easy",
        }
    ]

    result = run_delegation_memory(backend, scenarios, judge)
    assert result.correct == 0
    assert result.score == 0.0
