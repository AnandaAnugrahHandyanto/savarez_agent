# Hermes Python-only Optimization Completion Report
# Hermes Python-only 성능 최적화 개발 완료보고서

## 1. Purpose of This Document
## 1. 문서 목적

This document is the final completion report for the Python-only performance optimization work performed on `NousResearch/hermes-agent`.
이 문서는 `NousResearch/hermes-agent`에 대해 수행한 Python-only 성능 최적화 작업의 최종 완료보고서입니다.

It covers the following:
아래 내용을 포함합니다.

- the initial Rust direction and why it was abandoned
- the final Python-only optimization scope that was actually kept
- implementation details
- validation and benchmark methodology
- benchmark numbers and interpretation
- the current PR status
- remaining risks and follow-up observations
- 처음 시도했던 Rust 방향과 중단 이유
- 실제로 채택된 Python-only 최적화 범위
- 구현 상세
- 검증 및 벤치마크 절차
- 벤치마크 수치와 해석
- 현재 PR 상태
- 남은 리스크와 후속 관찰 포인트

## 2. Background
## 2. 작업 배경

The original problem statement was straightforward.
초기 문제의식은 단순했습니다.

- the `Responses API` hot path had relatively heavy storage and retrieval behavior
- long conversation chains and accumulated response history could increase cost over time
- the gateway could redundantly fetch the same media URL multiple times under concurrency
- `Responses API` hot path의 저장/조회 경로가 상대적으로 무거웠습니다.
- 긴 대화 체인과 누적된 응답 기록이 있을수록 비용이 커질 수 있었습니다.
- gateway에서 같은 media URL을 concurrency 상황에서 여러 번 중복 fetch할 수 있었습니다.

A Rust port was also explored at first. However, the actual experiment showed that partial Rust sidecar replacement did not produce acceptable ROI.
처음에는 Rust 포팅 가능성도 검토했습니다. 그러나 실제 실험 결과, 부분적인 Rust sidecar 치환은 받아들일 만한 ROI를 만들지 못했습니다.

The main reasons were:
핵심 이유는 아래와 같았습니다.

- the Python-to-Rust process boundary was too expensive
- JSON serialization/deserialization and subprocess pipe round-trips accumulated overhead
- for small work units, RPC cost outweighed compute savings
- Python과 Rust 사이의 프로세스 경계 비용이 너무 컸습니다.
- JSON serialize/deserialize와 subprocess pipe 왕복 비용이 누적됐습니다.
- 작은 작업 단위에서는 계산 이득보다 RPC 비용이 더 컸습니다.

Because of that, the direction changed as follows:
그래서 방향을 아래처럼 바꿨습니다.

- keep the language the same and make the real hot data path lighter
- change the storage structure instead of rewriting the system
- reduce duplicated work
- do not keep experiments that fail the performance test
- 언어를 바꾸지 않고 실제 hot data path를 더 가볍게 만듭니다.
- 시스템 재작성 대신 저장 구조를 바꿉니다.
- 중복 작업을 줄입니다.
- 성능 테스트를 통과하지 못한 실험은 남기지 않습니다.

## 3. Final Goal
## 3. 최종 목표

The final goal was not to make the codebase look more sophisticated.
최종 목표는 코드베이스를 더 그럴듯해 보이게 만드는 것이 아니었습니다.

The final goal was:
최종 목표는 아래였습니다.

1. make the real `Responses API` request path meaningfully faster
2. avoid semantic regressions or failure-rate regressions
3. avoid materially increasing operational complexity
4. prove the result with a reproducible methodology
1. 실제 `Responses API` 요청 경로를 유의미하게 빠르게 만들 것
2. 의미론 회귀나 실패율 회귀를 만들지 않을 것
3. 운영 복잡도를 크게 늘리지 않을 것
4. 재현 가능한 방법으로 결과를 입증할 것

## 4. Final Accepted Scope
## 4. 최종 채택 범위

Three changes were ultimately kept.
최종적으로 세 가지 변경을 유지했습니다.

### 4.1 ResponseStore storage redesign
### 4.1 ResponseStore 저장 구조 최적화

Previously, storing responses tended to carry conversation history in a relatively heavy form.
기존에는 응답 저장 시 대화 history를 상대적으로 무겁게 다루는 경향이 있었습니다.

This was changed to the following structure:
이를 아래 구조로 변경했습니다.

- keep periodic snapshot history nodes as checkpoints
- store later responses as delta history nodes
- preserve `previous_response_id` chaining semantics
- keep history nodes independent enough that deleting a parent response does not break child reconstruction
- 기준점 역할을 하는 snapshot history node를 유지합니다.
- 이후 응답은 delta history node로 저장합니다.
- `previous_response_id` 체인 의미론을 유지합니다.
- 부모 응답을 삭제해도 자식 체인 복원이 깨지지 않도록 history node를 독립적으로 유지합니다.

Expected benefits:
기대한 효과는 아래와 같습니다.

- reduce the cost of repeatedly handling full history during writes
- control reconstruction cost during reads
- flatten storage/retrieval growth as chains get longer
- 쓰기 시 전체 history를 매번 크게 다루는 부담을 줄입니다.
- 읽기 시 reconstruction 비용을 제어합니다.
- 체인이 길어질수록 저장/조회 비용 증가 폭을 완화합니다.

Primary modified files:
주요 수정 파일:

- `gateway/platforms/api_server.py`
- `tests/gateway/test_api_server.py`

### 4.2 Gateway media download deduplication
### 4.2 Gateway media download dedupe

When multiple requests hit the same media URL concurrently, the system can waste work by downloading the same file multiple times.
같은 media URL에 여러 요청이 동시에 들어오면, 같은 파일을 여러 번 다시 다운로드하는 낭비가 생길 수 있습니다.

To reduce that, the following were added:
이를 줄이기 위해 아래를 추가했습니다.

- same-key singleflight
- short-lived result cache
- cache keys that include cache directory information to avoid cross-environment contamination
- same-key singleflight
- short-lived result cache
- 환경 간 오염 방지를 위해 cache dir까지 포함한 cache key

Expected benefits:
기대한 효과는 아래와 같습니다.

- eliminate duplicate upstream fetches for identical media
- reduce external I/O waste under concurrency
- improve gateway hot path stability
- 동일 media에 대한 중복 upstream fetch 제거
- concurrency 상황에서 외부 I/O 낭비 감소
- gateway hot path 안정성 개선

Primary modified files:
주요 수정 파일:

- `gateway/platforms/base.py`
- `tests/gateway/test_media_download_retry.py`

### 4.3 Conservative handling of the compression path
### 4.3 Compression 경로의 보수적 정리

A generalized micro-cache was briefly added to `ContextCompressor` during the middle of the work.
중간 단계에서는 `ContextCompressor`에 일반화된 micro-cache를 잠시 넣었습니다.

However, the final microbenchmark showed that this path regressed rather than improved, so that experiment was removed from the final branch.
그러나 최종 microbenchmark에서 이 경로는 개선보다 회귀가 더 크게 나타났고, 그래서 해당 실험은 최종 브랜치에서 제거했습니다.

The final rule was simple:
최종 원칙은 단순했습니다.

- keep only the changes that actually measured well
- remove even plausible-looking optimizations if they regress in practice
- 실제로 이득이 측정된 변경만 유지합니다.
- 그럴듯해 보여도 실제로 회귀하면 제거합니다.

Related files:
관련 파일:

- `agent/context_compressor.py`
- `tests/agent/test_context_compressor.py`

## 5. What Was Deliberately Removed
## 5. 버린 것

An important part of this work is not just what was added, but what was explicitly removed.
이번 작업에서 중요한 점은 무엇을 추가했는지만이 아니라, 무엇을 명시적으로 버렸는지도 분명하다는 점입니다.

### 5.1 Rust sidecar direction
### 5.1 Rust sidecar 방향 중단

Why it was removed:
중단 이유:

- IPC and JSON boundary cost was too high for the chosen shape of integration
- for small work units like `ResponseStore` and `ContextCompressor`, the Python in-process path was faster
- the operational and maintenance complexity did not justify the measured outcome
- 현재 통합 방식에서는 IPC와 JSON 경계 비용이 너무 컸습니다.
- `ResponseStore`와 `ContextCompressor` 같은 작은 작업 단위에서는 Python 인프로세스 경로가 더 빨랐습니다.
- 운영 및 유지보수 복잡도를 감안하면 측정 결과를 정당화할 수 없었습니다.

Final outcome:
최종 정리:

- Rust code was removed from the final branch
- only the Python-only path remained
- Rust 코드는 최종 브랜치에서 제거했습니다.
- Python-only 경로만 남겼습니다.

### 5.2 Compression micro-cache experiment
### 5.2 Compression micro-cache 실험 제거

Why it was removed:
중단 이유:

- the microbenchmark showed a regression rather than a gain
- it was not directly paying off on the serving path that mattered most
- it did not justify staying in the branch
- microbenchmark 기준으로 회귀가 발생했습니다.
- 가장 중요한 serving path에 직접적인 이득을 주지 못했습니다.
- 브랜치에 남길 이유가 부족했습니다.

Final outcome:
최종 정리:

- the cache experiment was rolled back
- the final branch stayed conservative
- 해당 캐시 실험은 롤백했습니다.
- 최종 브랜치는 보수적으로 유지했습니다.

## 6. Where Real Users Should Feel the Improvement
## 6. 실사용 기준으로 어디가 빨라지는가

From a user perspective, this work matters most in the following situations.
사용자 관점에서 이번 최적화는 아래 상황에서 가장 의미가 큽니다.

1. when continuing a conversation across previous responses
2. when retrieving a previously stored response
3. when working in a session with accumulated response history
4. when the same media URL appears across multiple concurrent requests
1. 이전 응답을 이어서 계속 대화할 때
2. 저장된 응답을 다시 조회할 때
3. 응답 기록이 많이 누적된 세션에서 작업할 때
4. 같은 media URL이 여러 동시 요청에서 등장할 때

In practice, this means the optimization is more valuable for real agent sessions that keep going over time than for a single short one-off request.
즉, 이 최적화는 짧은 일회성 요청보다 시간이 지나면서 이어지는 실제 에이전트 세션에서 더 가치가 큽니다.

## 7. Benchmark Methodology
## 7. 벤치마크 설계

The most important thing about the benchmark was not just the number itself, but whether the number could be trusted.
이번 벤치마크에서 가장 중요했던 것은 숫자 자체보다 그 숫자를 믿을 수 있는가였습니다.

Local performance measurement is easy to contaminate. This repository uses local persistent state such as `~/.hermes/response_store.db`, and branch-to-branch state sharing can distort results.
로컬 성능 측정은 쉽게 오염됩니다. 이 저장소는 `~/.hermes/response_store.db` 같은 로컬 상태를 사용하고, 브랜치 간 상태 공유만으로도 결과가 왜곡될 수 있습니다.

Because of that, the final benchmark was rerun under the following conditions.
그래서 최종 수치는 아래 조건에서 다시 측정했습니다.

### 7.1 Measurement environment
### 7.1 측정 환경

- same machine
- same benchmark server harness
- same request payloads
- same concurrency
- same ApacheBench settings
- 동일 머신
- 동일 benchmark server harness
- 동일 요청 payload
- 동일 동시성
- 동일 ApacheBench 조건

### 7.2 Contamination control
### 7.2 오염 방지 조치

- separate `git worktree` for `main`
- separate `HOME` per branch
- no shared `~/.hermes/response_store.db` between branches
- `main`용 별도 `git worktree`
- 브랜치별 별도 `HOME`
- 브랜치 간 `~/.hermes/response_store.db` 공유 금지

### 7.3 API benchmark conditions
### 7.3 API benchmark 조건

- `ab -n 1000 -c 50`
- `POST /v1/responses`
- `GET /v1/responses/{id}`

### 7.4 Collected metrics
### 7.4 수집 지표

- latency
- throughput
- failed count
- non-2xx count
- RSS
- latency
- throughput
- failed count
- non-2xx count
- RSS

## 8. Final Benchmark Results
## 8. 최종 벤치마크 결과

The comparison below is `main` versus the final PR branch.
아래 비교는 `main`과 최종 PR 브랜치 기준입니다.

### 8.1 `POST /v1/responses`

- `main`: `98.650 ms/request`, `506.84 req/s`
- final branch: `67.667 ms/request`, `738.91 req/s`
- improvement: about `1.46x`
- `main`: `98.650 ms/request`, `506.84 req/s`
- 최종 브랜치: `67.667 ms/request`, `738.91 req/s`
- 개선폭: 약 `1.46x`

Interpretation:
해석:

- the create-response path became meaningfully faster
- this is not noise-level movement; it is significant on the real serving path
- 새 응답 생성 경로가 유의미하게 빨라졌습니다.
- 단순 오차 범위 수준이 아니라 실제 serving path에서 의미 있는 차이입니다.

### 8.2 `GET /v1/responses/{id}`

- `main`: `56.838 ms/request`, `879.69 req/s`
- final branch: `29.723 ms/request`, `1682.21 req/s`
- improvement: about `1.91x`
- `main`: `56.838 ms/request`, `879.69 req/s`
- 최종 브랜치: `29.723 ms/request`, `1682.21 req/s`
- 개선폭: 약 `1.91x`

Interpretation:
해석:

- the stored-response retrieval path improved by nearly `2x`
- this is the most visible result of the work
- 저장된 응답 조회 경로는 거의 `2x`에 가까운 개선이 나왔습니다.
- 이번 작업에서 가장 눈에 띄는 성과입니다.

### 8.3 Failure profile
### 8.3 실패율

- `POST`: `failed=0`, `non-2xx=0`
- `GET`: `failed=0`, `non-2xx=0`

Interpretation:
해석:

- the system did not get faster at the cost of benchmark-visible failures
- performance improved while preserving semantic stability in the benchmark run
- 빨라졌지만 벤치에서 보이는 실패율이 같이 나빠지지 않았습니다.
- 벤치 기준 의미론 안정성을 유지하면서 성능이 개선되었습니다.

### 8.4 Memory
### 8.4 메모리

- `main`: `37384 KB`
- final branch: `36964 KB`
- change: about `1.1%` lower
- `main`: `37384 KB`
- 최종 브랜치: `36964 KB`
- 변화: 약 `1.1%` 감소

Interpretation:
해석:

- memory improvement exists but is not the main story
- the real value of this work is latency/throughput improvement on the API hot path
- 메모리 개선은 있으나 핵심 성과는 아닙니다.
- 이번 작업의 핵심 가치는 API hot path의 latency/throughput 개선입니다.

### 8.5 Media dedupe synthetic benchmark
### 8.5 Media dedupe synthetic benchmark

For `25` concurrent requests to the same URL:
동일 URL에 대한 `25`개 동시 요청 기준:

- `main`: `network_calls=25`, `unique_paths=25`
- final branch: `network_calls=1`, `unique_paths=1`
- duplicate upstream fetch reduction: `96%`
- `main`: `network_calls=25`, `unique_paths=25`
- 최종 브랜치: `network_calls=1`, `unique_paths=1`
- 중복 upstream fetch 감소: `96%`

Interpretation:
해석:

- the mock wall-clock number alone is not enough to claim a total runtime win
- but collapsing redundant upstream fetches is still operationally meaningful
- mock wall-clock 숫자 하나만으로 전체 runtime 개선을 단정할 수는 없습니다.
- 그러나 redundant upstream fetch를 줄였다는 점 자체는 운영상 의미가 있습니다.

### 8.6 Compression microbenchmark
### 8.6 Compression microbenchmark

For `100` iterations:
`100`회 반복 기준:

- `main`: median `0.555 ms`, p95 `4.791 ms`
- final branch: median `0.656 ms`, p95 `5.130 ms`
- `main`: median `0.555 ms`, p95 `4.791 ms`
- 최종 브랜치: median `0.656 ms`, p95 `5.130 ms`

Interpretation:
해석:

- the compression path still shows a slight regression
- that is why the micro-cache experiment was removed and the branch was kept conservative
- the main value of the PR is still the `Responses API` hot path improvement
- compression 경로는 여전히 소폭 회귀가 있습니다.
- 그래서 micro-cache 실험을 제거하고 브랜치를 보수적으로 유지했습니다.
- 이 PR의 핵심 가치는 여전히 `Responses API` hot path 개선입니다.

## 9. Functional Validation and Tests
## 9. 기능 검증 및 테스트

Benchmark numbers alone are not enough, so semantic and functional regression coverage was also added.
성능 수치만으로는 충분하지 않기 때문에 의미론 회귀와 기능 회귀를 막기 위한 검증도 함께 수행했습니다.

### 9.1 ResponseStore / semantic behavior
### 9.1 ResponseStore / semantic behavior

Commands:
실행 명령:

```bash
python -m py_compile gateway/platforms/api_server.py tests/gateway/test_api_server.py
pytest -o addopts='' tests/gateway/test_api_server.py::TestResponseStore tests/gateway/test_api_server.py::TestResponsesEndpointSemantic -q
```

Result:
결과:

- `11 passed`

Covered behaviors:
검증한 핵심 동작:

- `previous_response_id` chaining
- instruction inheritance from previous responses
- child-chain reconstruction remains valid after parent deletion
- `previous_response_id` 체이닝
- 이전 응답으로부터 instruction 상속
- 부모 응답 삭제 후에도 child-chain reconstruction 유지

### 9.2 Context compressor
### 9.2 Context compressor

Commands:
실행 명령:

```bash
python -m py_compile agent/context_compressor.py tests/agent/test_context_compressor.py
pytest -o addopts='' tests/agent/test_context_compressor.py::TestShouldCompressPreflight tests/agent/test_context_compressor.py::TestCompress tests/agent/test_context_compressor.py::TestGetStatus -q
```

Result:
결과:

- `8 passed`

Explanation:
설명:

- the compression path was simplified and kept stable instead of forcing a speculative optimization through
- compression 경로는 추측성 최적화를 억지로 밀어넣지 않고 단순화와 안정성 유지 쪽으로 정리했습니다.

### 9.3 Media retry/dedupe + semantic response flow
### 9.3 Media retry/dedupe + semantic response flow

Commands:
실행 명령:

```bash
python -m py_compile gateway/platforms/base.py tests/gateway/test_media_download_retry.py
pytest -o addopts='' tests/gateway/test_media_download_retry.py::TestCacheImageFromUrl tests/gateway/test_media_download_retry.py::TestCacheAudioFromUrl tests/gateway/test_api_server.py::TestResponsesEndpointSemantic tests/test_anthropic_error_handling.py -q
```

Result:
결과:

- `24 passed`

Explanation:
설명:

- media dedupe behavior and semantic response flow were validated together
- media dedupe와 semantic response flow를 함께 검증했습니다.

## 10. Final Interpretation
## 10. 최종 해석

The most accurate reading of the result is the following.
이번 결과는 아래처럼 해석하는 것이 가장 정확합니다.

### 10.1 What clearly succeeded
### 10.1 성공한 부분

- the `Responses API` hot path became meaningfully faster
- `GET /v1/responses/{id}` improved to nearly `2x`
- `POST /v1/responses` also improved materially
- the benchmark showed no failure-rate regression
- duplicate media fetches were sharply reduced
- `Responses API` hot path는 실제로 의미 있게 빨라졌습니다.
- `GET /v1/responses/{id}`는 거의 `2x` 수준까지 개선됐습니다.
- `POST /v1/responses`도 충분히 의미 있는 개선이 나왔습니다.
- 벤치 기준 실패율 회귀가 없었습니다.
- 중복 media fetch를 크게 줄였습니다.

### 10.2 What was intentionally left out
### 10.2 의도적으로 포기한 부분

- the Rust sidecar direction
- the compression micro-cache direction
- Rust sidecar 방향
- compression micro-cache 방향

### 10.3 Bottom-line conclusion
### 10.3 결론

This was not an attempt to improve every microbenchmark.
이 작업은 모든 microbenchmark를 개선하려는 시도가 아니었습니다.

Instead, it was closer to this:
대신 아래에 더 가깝습니다.

- keep only the changes that produced clear performance gains on the real service path
- remove directions that had poor ROI or measurable regressions
- end up with a conservative but defensible optimization set
- 실제 서비스 경로에서 명확한 성능 개선을 낸 변경만 남깁니다.
- ROI가 낮거나 회귀가 있던 방향은 제거합니다.
- 보수적이지만 설득 가능한 최적화 세트로 정리합니다.

In other words, this PR does not win by rewriting everything. It wins by keeping only the changes that measured well on the path users actually exercise.
즉, 이 PR은 모든 것을 재작성해서 승부한 것이 아니라 사용자가 실제로 밟는 경로에서 측정상 이득이 난 변경만 남겨서 승부한 것입니다.

## 11. PR Status
## 11. PR 현황

The current PR is:
현재 PR은 아래와 같습니다.

- `https://github.com/NousResearch/hermes-agent/pull/4215`

Title:
제목:

- `Optimize Responses API hot path without Rust sidecar`

Current status summary:
현재 상태 요약:

- the PR is open
- there is no merge conflict
- final merge has not happened yet
- maintainer review and decision are still pending
- PR은 open 상태입니다.
- merge conflict는 없습니다.
- 최종 merge는 아직 아닙니다.
- maintainer 리뷰와 판단이 남아 있습니다.

## 12. Remaining Risks and Follow-up Points
## 12. 남은 리스크와 관찰 포인트

### 12.1 Compression path
### 12.1 Compression 경로

- this is not the main win of the PR, but a slight microbenchmark regression still remains
- because the real value is in the `Responses API` hot path, scope control mattered more than over-optimizing this path in this PR
- 현재 PR의 핵심 성과는 아니지만 microbenchmark 기준 소폭 회귀가 남아 있습니다.
- 실제 가치는 `Responses API` hot path에 있으므로, 이번 PR에서는 이 경로를 과도하게 최적화하기보다 범위 통제가 더 중요했습니다.

### 12.2 Media dedupe under real traffic
### 12.2 실제 트래픽에서의 media dedupe 효과

- the synthetic benchmark does not fully prove a wall-clock win by itself
- but real upstream fetch collapse may still be important operationally
- after merge, this should ideally be observed under real traffic
- synthetic benchmark만으로 wall-clock 이득을 완전히 입증한 것은 아닙니다.
- 그러나 실제 upstream fetch collapse 효과는 운영상 여전히 중요할 수 있습니다.
- merge 후 실제 트래픽 환경에서 관찰하는 것이 좋습니다.

### 12.3 Expected user-visible impact
### 12.3 실제 사용자 체감 포인트

Users are most likely to notice the result in the following cases:
사용자는 아래 경우에서 가장 체감할 가능성이 큽니다.

- continuing long-running sessions
- revisiting stored responses
- repeatedly handling the same media URLs
- 긴 세션을 이어서 대화할 때
- 저장된 응답을 다시 볼 때
- 같은 media URL이 반복해서 등장할 때

## 13. Final Summary
## 13. 최종 요약

The entire project can be summarized in one sentence:
이번 작업의 핵심은 한 문장으로 요약할 수 있습니다.

"Instead of rewriting Hermes in Rust, reduce the real Python-side bottlenecks in storage, retrieval, and duplicate media fetches, and improve the `Responses API` hot path by an amount that can actually be measured and defended."
"Hermes를 Rust로 크게 다시 쓰는 대신, Python 쪽의 실제 병목인 저장, 조회, 중복 media fetch를 줄여서 `Responses API` hot path를 측정 가능하고 방어 가능한 수준으로 개선했다."

Summary numbers:
요약 수치:

- `POST /v1/responses`: about `1.46x` faster
- `GET /v1/responses/{id}`: about `1.91x` faster
- `failed=0`, `non-2xx=0`
- duplicate upstream media fetches reduced by `96%`
- `POST /v1/responses`: 약 `1.46x` 개선
- `GET /v1/responses/{id}`: 약 `1.91x` 개선
- `failed=0`, `non-2xx=0`
- media duplicate upstream fetch: `96%` 감소

The main significance of this PR is that it demonstrates a reproducible, measurable performance improvement on a real serving path in a large, widely used open-source project.
이번 PR의 가장 큰 의미는 규모가 크고 널리 사용되는 오픈소스 프로젝트에서 실제 serving path 기준으로 재현 가능하고 측정 가능한 성능 개선을 입증했다는 점입니다.
