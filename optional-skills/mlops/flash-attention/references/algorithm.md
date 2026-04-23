# Flash Attention Algorithm Reference

Covers the core algorithmic innovations in Flash Attention: IO-aware tiling, selective recomputation,
and the resulting IO complexity improvements over standard attention.

---

## Standard Attention: The IO Problem

Standard attention computes:

```
S = Q @ K^T / sqrt(d_k)      # [N, N] — written to HBM
P = softmax(S)                 # [N, N] — written to HBM
O = P @ V                      # [N, d] — output
```

For sequence length N and head dimension d, this requires:
- **O(N²)** memory for S and P (written and read from HBM)
- **O(N²d)** HBM reads/writes total
- At N=4096, d=64: ~1GB of HBM traffic per attention head

The bottleneck is not FLOPs — it is HBM bandwidth. Modern GPUs (A100: 2TB/s HBM, 312 TFLOPS bf16)
are memory-bandwidth-bound on standard attention for sequences longer than ~512 tokens.

---

## Flash Attention: IO-Aware Tiling

Flash Attention avoids materializing the full N×N attention matrix by computing attention in tiles
that fit in SRAM (fast on-chip memory, ~192KB on A100).

### Tiling Strategy

Split Q, K, V into blocks along the sequence dimension:

```
Q → blocks of size B_r × d    (B_r = row block size)
K → blocks of size B_c × d    (B_c = column block size)
V → blocks of size B_c × d
```

Block sizes are chosen so that each (Q_block, K_block, V_block) triple fits in SRAM:

```
B_r = B_c = floor(SRAM_size / (4 × d))
```

### Online Softmax

The key algorithmic challenge: softmax over a full row requires the row maximum, which is not known
while processing tiles. Flash Attention uses an **online softmax** that maintains running statistics
and corrects them tile by tile.

For each query block `Q_i`, iterate over key/value blocks `K_j`, `V_j`:

```python
# Running statistics (initialized per query block)
m_i = -inf        # running row maximum
l_i = 0.0         # running softmax denominator
O_i = zeros(d)    # running output accumulator

for j in range(num_kv_blocks):
    S_ij = Q_i @ K_j.T / sqrt(d)          # [B_r, B_c] — computed in SRAM

    m_ij = max(S_ij, dim=-1)               # new local max
    m_new = max(m_i, m_ij)                 # updated global max

    # Correction factors
    alpha = exp(m_i - m_new)
    beta  = exp(m_ij - m_new)

    P_ij = exp(S_ij - m_new.unsqueeze(-1)) # local softmax numerator (unscaled)

    # Update accumulators
    l_i = alpha * l_i + beta * P_ij.sum(-1)
    O_i = alpha * O_i + P_ij @ V_j

# Final normalization
O_i = O_i / l_i.unsqueeze(-1)
```

After all tiles, `O_i` holds the exact softmax attention output for query block `Q_i` — numerically
identical to standard attention (up to floating-point order-of-operations).

### IO Complexity

| Metric              | Standard Attention      | Flash Attention          |
|---------------------|-------------------------|--------------------------|
| HBM reads/writes    | O(N²d)                  | O(N²d / M) × O(Nd)      |
| Peak HBM memory     | O(N²)                   | O(N)                     |
| Extra SRAM usage    | —                       | O(B_r × d + B_c × d)    |
| FLOP count          | O(N²d)                  | O(N²d) (same)            |

Where M = SRAM size. The HBM traffic reduction is proportional to M/d — for A100 (M≈192KB, d=64),
this yields roughly 5–10× fewer HBM reads/writes, which translates directly into wallclock speedup.

---

## Recomputation in the Backward Pass

Standard attention stores the full N×N attention weight matrix P for the backward pass
(needed to compute gradients). This is the dominant memory cost for large sequences.

Flash Attention eliminates this storage via **selective recomputation**:

1. During the forward pass, store only the output `O` and the softmax statistics `(m, l)` — both O(N).
2. During the backward pass, **recompute** the attention tiles on the fly from Q, K, V (re-running
   the forward tiling loop) rather than reading stored P from HBM.

**Why recomputation wins:**

- Recomputing a tile costs FLOPs (cheap on modern GPUs).
- Storing/loading P costs HBM bandwidth (the actual bottleneck).
- For A100: recomputing P is faster than loading it from HBM when N > ~1024.

Memory saved: O(N²) → O(N) for the activation checkpoints.

```
Stored in forward pass:
  O      [N, d]   — output (always needed)
  m      [N]      — row maxima
  l      [N]      — softmax denominators

NOT stored (recomputed in backward):
  S      [N, N]   — raw attention scores
  P      [N, N]   — attention weights
```

---

## Flash Attention 2: Parallelism Improvements

Flash Attention 2 (Dao, 2023 / ICLR 2024) refines the original with better GPU utilization:

### Work Partitioning

FA1 partitioned work across warps in a way that required synchronization for the online softmax
reduction. FA2 restructures the loop order:

- **Outer loop over Q blocks** — parallelized across thread blocks (no cross-block communication needed).
- **Inner loop over KV blocks** — sequential within each thread block, keeping softmax state local.

This eliminates inter-warp synchronization on the softmax reduction, improving SM utilization
from ~25–40% (FA1) to ~50–73% (FA2) on A100.

### Reduced Non-Matmul FLOPs

FA2 reorganizes the rescaling operations to minimize non-matmul instructions (exp, multiply-add).
Non-matmul FLOPs run at ~1/16 the throughput of matmul FLOPs on A100 tensor cores, so reducing
them increases effective throughput even without reducing total FLOP count.

### Sequence Parallelism Support

FA2 supports splitting the sequence across multiple GPUs (sequence parallelism), with each GPU
computing attention for a subset of query positions. The softmax statistics can be all-reduced
across ranks to produce globally correct outputs.

---

## Flash Attention 3 (H100)

For H100 GPUs, Flash Attention 3 adds:

- **FP8 support** — Uses H100's FP8 tensor cores for a further 1.5–2× speedup (with precision tradeoff).
- **Asynchronous pipelines** — Overlaps WGMMA (tensor core matmul) with softmax computation using
  H100's asynchronous execution model.
- **Persistent kernels** — Keeps thread blocks resident across multiple attention tiles, reducing
  kernel launch overhead.

FP8 attention is lossy — suitable for inference, not recommended for training without careful
calibration. Use `attn_implementation="flash_attention_3"` only on H100/H200 hardware.

---

## Numerical Stability

Flash Attention is numerically equivalent to standard attention, not merely approximate.

The online softmax identity used is:

```
softmax([a, b]) = softmax([a - c, b - c])  for any constant c
```

By subtracting the running maximum at each tile, Flash Attention ensures exp() arguments stay
negative (preventing overflow) while producing the same final result as computing softmax over
the full row at once.

**Float16 vs bfloat16:**
- float16 has higher precision (10-bit mantissa) but smaller range (max ~65504).
- bfloat16 has lower precision (7-bit mantissa) but A100/H100 tensor-core range (same as float32).
- Flash Attention accumulates into float32 internally even when inputs are float16/bfloat16.
- For sequences > 8192 tokens, bfloat16 is safer (less risk of overflow in intermediate sums).

---

## Verification

To confirm Flash Attention is producing numerically correct outputs:

```python
import torch
import torch.nn.functional as F
import math

def standard_attention(q, k, v, causal=False):
    d = q.shape[-1]
    scores = (q @ k.transpose(-2, -1)) / math.sqrt(d)
    if causal:
        N = q.shape[-2]
        mask = torch.triu(torch.ones(N, N, device=q.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))
    weights = torch.softmax(scores.float(), dim=-1).to(q.dtype)
    return weights @ v

# Test inputs
q, k, v = [torch.randn(2, 8, 512, 64, device='cuda', dtype=torch.float16) for _ in range(3)]

out_flash    = F.scaled_dot_product_attention(q, k, v, is_causal=True)
out_standard = standard_attention(q, k, v, causal=True)

max_diff = (out_flash.float() - out_standard.float()).abs().max().item()
print(f"Max absolute difference: {max_diff:.2e}")
# Expected: < 1e-2 for float16 (rounding differences, not algorithmic error)
# Typical:    ~1e-3 to 5e-3
```

Differences above 0.1 indicate a bug (wrong mask, wrong scale factor, or dtype mismatch),
not inherent Flash Attention approximation error.

---

## References

- Dao et al., "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness" (NeurIPS 2022)
- Dao, "FlashAttention-2: Faster Attention with Better Parallelism and Work Partitioning" (ICLR 2024)
- Shah et al., "FlashAttention-3: Fast and Accurate Attention with Asynchrony and Low-precision" (2024)
- flash-attn source: https://github.com/Dao-AILab/flash-attention
