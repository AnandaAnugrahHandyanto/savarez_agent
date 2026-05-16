## 2025-05-12 - base_url_hostname caching
**Learning:** Repeated hostname lookups for identical endpoints are a bottleneck when evaluating API configurations, provider constraints, and routing checks for every API call/feature toggle detection.
**Action:** Use `@functools.lru_cache` on functions that do string parsing and are called frequently with the same arguments, like URL parsing helpers.

## 2024-05-16 - [Fast batch tokenization in python]
**Learning:** HuggingFace `tokenizer` batch encoding (passing a list of texts to `tokenizer(texts)`) is approximately 3x faster than calling `tokenizer.encode(text)` in a loop, as it delegates the iteration down to the optimized Rust implementation within the `transformers` library. This is critical when computing token counts across multiple turns within a chat trajectory.
**Action:** When working with tokenizers and a list of texts, prefer passing the entire list to the tokenizer at once rather than looping over items, making sure to fallback gracefully to character limits if the tokenizer object is absent or errors out.
