Testing error handling blocks deep inside AIAgent.run_conversation() is challenging because of the large amount of tightly coupled initialization logic and dependencies. It is much easier to define tests inside test_run_agent.py and reuse the existing uninitialized AIAgent instances and helper functions (like _mock_response), then mock _interruptible_api_call directly to return the required responses and avoid heavy stubbing requirements.

When applying inline logic fixes, replacing only the specific changed block using standard string manipulation or simple sed is preferable over using formatters that rewrite the entire file (which causes unacceptable Git diff pollution and code review rejection).

## 2024-05-16 - [Fast batch tokenization in python]
**Learning:** HuggingFace `tokenizer` batch encoding (passing a list of texts to `tokenizer(texts)`) is approximately 3x faster than calling `tokenizer.encode(text)` in a loop, as it delegates the iteration down to the optimized Rust implementation within the `transformers` library. This is critical when computing token counts across multiple turns within a chat trajectory.
**Action:** When working with tokenizers and a list of texts, prefer passing the entire list to the tokenizer at once rather than looping over items, making sure to fallback gracefully to character limits if the tokenizer object is absent or errors out.
