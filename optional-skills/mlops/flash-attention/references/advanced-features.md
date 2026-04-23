# Flash Attention Advanced Features Reference

Covers rotary embeddings (RoPE), ALiBi positional bias, paged KV cache, and custom attention masks
with Flash Attention — including implementation patterns and common pitfalls.

---

## Rotary Embeddings (RoPE)

Rotary Position Embedding encodes position by rotating query and key vectors in a 2D plane.
It is the default positional encoding for Llama, Mistral, Qwen, Gemma, and most modern LLMs.

### How RoPE Works

For a query vector `q` at position `m`, RoPE applies a rotation matrix `R_m`:

```
q_rotated[2i]   = q[2i]   * cos(m * θ_i) - q[2i+1] * sin(m * θ_i)
q_rotated[2i+1] = q[2i]   * sin(m * θ_i) + q[2i+1] * cos(m * θ_i)
```

where `θ_i = 1 / (base ** (2i / d))` and `base=10000` (or 500000 for extended-context models).

The key property: `q_m^T k_n` depends only on `m - n` (relative position), giving RoPE its
extrapolation and length-generalization behavior.

### RoPE with Flash Attention

Flash Attention applies RoPE **before** the attention kernel — the rotated Q and K are passed in,
not the raw embeddings. This is already handled internally by HuggingFace and most frameworks.

**Manual RoPE application (for custom attention):**

```python
import torch

def apply_rope(x, cos, sin, position_ids):
    """Apply RoPE to query or key tensor.
    
    Args:
        x:            [batch, seq, heads, head_dim]
        cos, sin:     [1, max_seq, 1, head_dim]  — precomputed rotation tables
        position_ids: [batch, seq]
    """
    cos = cos.squeeze(0).squeeze(1)[position_ids]  # [batch, seq, head_dim]
    sin = sin.squeeze(0).squeeze(1)[position_ids]

    # Rotate half-dimensions
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
    x_rotated = torch.cat([-x2, x1], dim=-1)

    return (x * cos.unsqueeze(2)) + (x_rotated * sin.unsqueeze(2))


# Usage with flash_attn
from flash_attn import flash_attn_func

q_rot = apply_rope(q, cos, sin, position_ids)
k_rot = apply_rope(k, cos, sin, position_ids)

# q_rot, k_rot: [batch, seq, heads, head_dim]
out = flash_attn_func(q_rot, k_rot, v, causal=True)
```

### Sliding Window + RoPE (Mistral-style)

For sliding window attention, only the local window positions are relevant. RoPE position IDs
must match the actual token positions in the original sequence, not local window indices:

```python
# Correct: use global positions
position_ids = torch.arange(seq_len, device=device).unsqueeze(0)

# Wrong: resets positions within each window
position_ids = torch.arange(window_size, device=device).unsqueeze(0)
```

Using local window indices causes position aliasing — the model sees the same relative positions
for all windows, breaking long-range coherence.

---

## ALiBi (Attention with Linear Biases)

ALiBi replaces positional embeddings with a learned linear bias added to attention scores before
softmax. Used in MPT, BLOOM, and some OPT variants.

### ALiBi Formula

```
Score(q_m, k_n) = (q_m · k_n) / sqrt(d) - |m - n| * slope_h
```

Where `slope_h` is a head-specific slope: `slope_h = 2^(-8h/H)` for head `h` out of `H` total heads.

Heads with smaller slopes attend further; heads with larger slopes focus locally.

### ALiBi with Flash Attention (flash-attn library)

The `flash-attn` library supports ALiBi via the `alibi_slopes` argument:

```python
from flash_attn import flash_attn_func
import torch

def get_alibi_slopes(num_heads):
    """Compute ALiBi slopes for each attention head."""
    # From the ALiBi paper (Press et al., 2022)
    def get_slopes_power_of_2(n):
        start = 2 ** (-(2 ** -(torch.log2(torch.tensor(n, dtype=torch.float)) - 3)))
        ratio = start
        return [start * ratio**i for i in range(n)]

    if num_heads <= 0:
        raise ValueError("num_heads must be positive")

    closest_power_of_2 = 2 ** math.floor(math.log2(num_heads))
    slopes = get_slopes_power_of_2(closest_power_of_2)

    if closest_power_of_2 != num_heads:
        # Interpolate for non-power-of-2 head counts
        extra_slopes = get_slopes_power_of_2(2 * closest_power_of_2)[0::2]
        slopes.extend(extra_slopes[:num_heads - closest_power_of_2])

    return torch.tensor(slopes, dtype=torch.float32)


import math

num_heads = 16
alibi_slopes = get_alibi_slopes(num_heads).cuda()   # [num_heads]

# q, k, v: [batch, seq, num_heads, head_dim]
out = flash_attn_func(
    q, k, v,
    alibi_slopes=alibi_slopes,
    causal=True,
)
```

**ALiBi is not compatible with RoPE** — use one or the other, not both.

### ALiBi with PyTorch SDPA (fallback)

PyTorch's `scaled_dot_product_attention` does not natively support ALiBi. Use a manual bias matrix:

```python
import torch
import torch.nn.functional as F

def make_alibi_bias(num_heads, seq_len, device, dtype):
    slopes = get_alibi_slopes(num_heads).to(device, dtype)  # [H]
    positions = torch.arange(seq_len, device=device)
    bias = -slopes.unsqueeze(-1) * (positions.unsqueeze(0) - positions.unsqueeze(1)).abs()
    # bias: [H, seq, seq]
    return bias.unsqueeze(0)  # [1, H, seq, seq]

bias = make_alibi_bias(num_heads=16, seq_len=q.shape[1], device=q.device, dtype=q.dtype)

# q, k: [batch, heads, seq, head_dim]
out = F.scaled_dot_product_attention(q, k, v, attn_mask=bias)
```

This materializes the full N×N bias and loses Flash Attention's memory savings — use the
`flash_attn_func` + `alibi_slopes` path whenever possible.

---

## Paged KV Cache

Paged KV cache (from vLLM's PagedAttention) avoids contiguous memory allocation for KV caches
during inference. Instead of pre-allocating a fixed [max_seq_len, d] buffer per sequence,
memory is allocated in **pages** (blocks) and mapped on demand.

### Why Paged KV Cache Matters

Standard KV cache pre-allocates `max_seq_len × num_heads × head_dim × 2 × sizeof(dtype)` bytes
per sequence. For 1000 concurrent sequences with max_len=8192, Llama-70B:

```
1000 × 8192 × 8 × 128 × 2 × 2 bytes ≈ 34 GB  (most of it wasted for shorter sequences)
```

Paged allocation reduces this waste to ~4% fragmentation in practice.

### PagedAttention with flash-attn

```python
from flash_attn.flash_attn_interface import flash_attn_with_kvcache

# block_table: [batch, max_blocks_per_seq] — maps sequence positions to physical blocks
# k_cache, v_cache: [num_blocks, block_size, num_heads, head_dim]

out = flash_attn_with_kvcache(
    q,                    # [batch, seq_q, num_heads, head_dim]
    k_cache,              # [num_blocks, block_size, num_kv_heads, head_dim]
    v_cache,              # [num_blocks, block_size, num_kv_heads, head_dim]
    k=k_new,              # [batch, seq_new, num_kv_heads, head_dim] — new KV to append
    v=v_new,
    cache_seqlens=cache_seqlens,   # [batch] — current KV length per sequence
    block_table=block_table,       # [batch, max_blocks]
    causal=True,
)
```

**Block size trade-offs:**
- Smaller blocks (e.g., 8–16 tokens): less fragmentation, more overhead per block.
- Larger blocks (e.g., 32–64 tokens): better memory efficiency, more waste per partially-filled block.
- vLLM default: 16 tokens/block.

### Prefix Caching with Paged KV

For shared system prompts (common in production), prefix blocks can be shared across sequences:

```python
# Two sequences share the same system prompt prefix
# Their block_tables point to the same physical blocks for positions 0..prefix_len
block_table_seq1 = [shared_block_0, shared_block_1, ..., unique_block_for_seq1]
block_table_seq2 = [shared_block_0, shared_block_1, ..., unique_block_for_seq2]
```

The shared blocks are read-only — never written after the prefix is cached. This requires the
inference engine (vLLM, SGLang) to manage block reference counts.

---

## Custom Attention Masks

### Causal (Autoregressive) Mask

The most common mask — each position attends only to itself and previous positions:

```python
# PyTorch SDPA (automatic causal mask)
out = F.scaled_dot_product_attention(q, k, v, is_causal=True)

# flash-attn library
out = flash_attn_func(q, k, v, causal=True)
```

Never construct a manual causal mask and pass it as `attn_mask` — this disables the Flash Attention
kernel and falls back to standard O(N²) memory attention.

### Sliding Window Attention

Each position attends to the previous `window_size` tokens only. Used in Mistral, Phi, and
long-context models to reduce KV cache size.

```python
from flash_attn import flash_attn_func

window_size = 4096  # attend to 4096 tokens before each position

out = flash_attn_func(
    q, k, v,
    causal=True,
    window_size=(window_size, 0),  # (left_window, right_window)
)
```

`window_size=(-1, -1)` disables sliding window (full attention). `window_size=(w, 0)` gives
a left-only window (causal). `window_size=(w, w)` gives a symmetric window (bidirectional local).

### Variable-Length / Packed Sequences

For training efficiency, pack multiple sequences of different lengths into a single batch dimension
without padding. Flash Attention supports this natively via `cu_seqlens` (cumulative sequence lengths).

```python
from flash_attn import flash_attn_varlen_func

# Pack [seq1_tokens, seq2_tokens, seq3_tokens] into one tensor (no padding)
# cu_seqlens: cumulative token counts, shape [batch+1]
#   e.g., [0, 128, 384, 512] for sequences of length 128, 256, 128

out = flash_attn_varlen_func(
    q,              # [total_tokens, num_heads, head_dim]
    k,              # [total_tokens, num_kv_heads, head_dim]
    v,              # [total_tokens, num_kv_heads, head_dim]
    cu_seqlens_q,   # [batch + 1]
    cu_seqlens_k,   # [batch + 1]
    max_seqlen_q,   # int — longest q sequence
    max_seqlen_k,   # int — longest k sequence
    causal=True,
)
# out: [total_tokens, num_heads, head_dim]
```

This avoids the wasted compute on padding tokens and enables training with mixed-length batches
at near-100% GPU utilization.

### Document Masking (Multi-Document Batches)

To process a batch of independent documents without cross-document attention leaking:

```python
# Build cu_seqlens from document boundaries
doc_lengths = [512, 1024, 768]   # tokens per document
cu_seqlens = torch.tensor([0] + list(torch.cumsum(torch.tensor(doc_lengths), dim=0)),
                           dtype=torch.int32, device='cuda')

out = flash_attn_varlen_func(
    q, k, v,
    cu_seqlens_q=cu_seqlens,
    cu_seqlens_k=cu_seqlens,
    max_seqlen_q=max(doc_lengths),
    max_seqlen_k=max(doc_lengths),
    causal=False,    # bidirectional within each document
)
```

Documents are isolated — attention never crosses document boundaries.

### Arbitrary Sparse Masks (Unsupported by Flash Attention Kernel)

Flash Attention's kernel does not support arbitrary sparse boolean masks. If you need a custom
non-causal, non-sliding-window mask:

```python
# Option A: Use standard SDPA with a mask tensor (loses memory efficiency)
mask = build_custom_mask(seq_len)         # [batch, heads, seq, seq] bool or float
out = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)

# Option B: Use xformers memory-efficient attention (more flexible masking)
from xformers.ops import memory_efficient_attention, LowerTriangularMask
out = memory_efficient_attention(q, k, v, attn_bias=LowerTriangularMask())
```

For structured sparse patterns (block-sparse, strided), consider using `triton`-based custom kernels
or the `flash-attn` block-sparse API (experimental, not stable across versions).

---

## Multi-Query Attention (MQA) and Grouped Query Attention (GQA)

Modern architectures (Llama 3, Mistral, Gemma) use GQA to reduce KV cache size while preserving
model quality. Flash Attention supports GQA natively.

```python
from flash_attn import flash_attn_func

# GQA: 32 query heads, 8 KV heads (ratio 4:1)
num_q_heads  = 32
num_kv_heads = 8
head_dim     = 128

q = torch.randn(batch, seq, num_q_heads,  head_dim, device='cuda', dtype=torch.bfloat16)
k = torch.randn(batch, seq, num_kv_heads, head_dim, device='cuda', dtype=torch.bfloat16)
v = torch.randn(batch, seq, num_kv_heads, head_dim, device='cuda', dtype=torch.bfloat16)

# flash_attn_func detects GQA from the head count mismatch automatically
out = flash_attn_func(q, k, v, causal=True)
# out: [batch, seq, num_q_heads, head_dim]
```

The flash-attn kernel handles the key/value broadcast internally without materializing the expanded
`[batch, seq, num_q_heads, head_dim]` K/V tensors — saving `num_q_heads / num_kv_heads`× KV memory
vs naive expansion.

---

## Common Pitfalls

**Using `attn_mask` with Flash Attention kernel disabled:**
`F.scaled_dot_product_attention` disables the Flash Attention backend if `attn_mask` is a tensor
(not None). Verify with:
```python
with torch.backends.cuda.sdp_kernel(enable_flash=True, enable_math=False):
    out = F.scaled_dot_product_attention(q, k, v, attn_mask=mask)
    # Will raise if Flash Attention can't be used
```

**Wrong tensor layout for flash-attn library:**
`flash_attn_func` expects `[batch, seq, heads, head_dim]` (heads after seq).
PyTorch's native SDPA expects `[batch, heads, seq, head_dim]` (heads before seq).
Permuting the wrong way is a silent correctness bug — outputs look reasonable but are wrong.

**Sliding window with position IDs reset:**
See the RoPE section above. Always use global sequence positions, not local window indices.

**FP8 on non-H100 hardware:**
Flash Attention 3 FP8 mode (`attn_implementation="flash_attention_3"`) requires H100/H200 GPU.
On A100, it falls back silently to BF16 or raises depending on the version. Check `torch.cuda.get_device_capability()` ≥ (9, 0) before enabling.
