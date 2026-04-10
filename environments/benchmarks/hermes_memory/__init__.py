"""
HermesMemory - A superior AI memory system benchmarked against MemPalace.

Key innovations over MemPalace:
1. Dual-retriever: BM25 + semantic late fusion (MemPalace uses only semantic)
2. Multi-granularity: indexes both sessions AND individual turns
3. Entity coreference: cross-session entity linking with simple spaCy-based resolution
4. Learned weights: training on dev set to learn optimal fusion weights
5. Hermes-native: built for the Hermes agent ecosystem with MCP tools
"""

__version__ = "1.0.0"
