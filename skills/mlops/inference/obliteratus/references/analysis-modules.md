# OBLITERATUS Analysis Modules — Reference

OBLITERATUS documents 15 headline analysis modules in its README. The source tree also contains additional advanced analysis helpers and utilities. Treat the 15 modules below as the stable, user-facing reference; mention newer helper files only after checking the installed OBLITERATUS version.

## Core Analysis (Run These First)

### 1. Alignment Imprint Detection (`alignment_imprint.py`)
Fingerprints whether a model was trained via DPO, RLHF, CAI, or SFT. This helps choose extraction defaults because different alignment methods leave different geometry in the activation space.

### 2. Concept Cone Geometry (`concept_geometry.py`)
Determines whether refusal is represented as one linear direction or a polyhedral cone. Single-direction models respond well to `basic`; polyhedral models need `advanced`, `surgical`, or more directions.

### 3. Refusal Logit Lens (`logit_lens.py`)
Identifies the layer where a model begins preferring refusal tokens by decoding intermediate representations into token space.

### 4. Ouroboros Detection (`anti_ouroboros.py`)
Predicts whether a model may reconstruct refusal behavior after excision. High self-repair risk means additional refinement passes or a more targeted method may be needed.

### 5. Causal Tracing (`causal_tracing.py`)
Uses activation patching to identify which layers, attention heads, or MLP components are causally necessary for refusal behavior.

## Geometric Analysis

### 6. Cross-Layer Alignment (`cross_layer.py`)
Measures how refusal directions align across layers. High alignment means removal is simpler; low alignment suggests layer-specific handling.

### 7. Residual Stream Decomposition (`residual_stream.py`)
Breaks refusal signal into attention and MLP contributions, helping decide whether to target attention heads, MLPs, or both.

### 8. Riemannian Manifold Geometry (`riemannian_manifold.py`)
Analyzes local weight-manifold geometry around refusal directions. Useful for research-grade decisions about projection aggressiveness.

### 9. Whitened SVD (`whitened_svd.py`)
Uses covariance-normalized SVD to separate true refusal signal from ordinary activation variance.

## Probing and Classification

### 10. Activation Probing (`activation_probing.py`)
Measures residual refusal signal strength before and after abliteration.

### 11. Probing Classifiers (`probing_classifiers.py`)
Trains classifiers to detect refusal in hidden states. After successful abliteration, classifier performance should approach chance.

### 12. Activation Patching (`activation_patching.py`)
Swaps activations between refused and complied runs to identify components sufficient for refusal behavior.

## Transfer and Robustness

### 13. Cross-Model Transfer (`cross_model_transfer.py`)
Tests whether refusal directions from one model transfer to another architecture.

### 14. Defense Robustness (`defense_robustness.py`)
Evaluates how robust refusal mechanisms are and how entangled they are with useful capabilities.

### 15. Spectral Certification (`spectral_certification.py`)
Uses spectral analysis to estimate whether the major refusal components were addressed. Treat this as a diagnostic signal, not as a replacement for refusal-rate and perplexity checks.

## Additional Advanced Helpers

Recent OBLITERATUS releases include additional files such as `sae_abliteration.py`, `steering_vectors.py`, `leace.py`, `sparse_surgery.py`, `conditional_abliteration.py`, `wasserstein_optimal.py`, `wasserstein_transfer.py`, `tuned_lens.py`, `multi_token_position.py`, and visualization utilities. These can be useful for researchers, but their availability and CLI exposure may vary by installed version.

## Running Analysis

### Via CLI
```bash
# Run analysis from a YAML config
obliteratus run analysis-study.yaml --preset quick

# Common study presets:
# quick      — Fast sanity check
# jailbreak  — Refusal circuit localization
# guardrail  — Guardrail robustness evaluation
# attention  — Attention-head contribution analysis
# knowledge  — FFN importance mapping
# full       — Complete analysis
```

### Via YAML Config
Load the template with: `skill_view(name="obliteratus", file_path="templates/analysis-study.yaml")`
