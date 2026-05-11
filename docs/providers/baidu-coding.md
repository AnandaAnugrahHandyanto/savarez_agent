# Baidu Coding Plan Provider

Native provider support for [Baidu Qianfan Coding Plan](https://cloud.baidu.com/doc/qianfan/s/imlg0beiu) (百度千帆编码计划) — a subscription-based AI coding service from Baidu Cloud.

## Quick Start

```bash
# Set your Coding Plan API key (starts with sk-sp-)
export BAIDU_CODING_API_KEY=sk-sp-xxxxx
```

```yaml
# config.yaml
model:
  default: glm-5.1
  provider: baidu-coding
```

## Configuration

| Env var | Required | Description |
|---------|----------|-------------|
| `BAIDU_CODING_API_KEY` | Yes (or `BAIDU_API_KEY`) | Coding Plan API key (`sk-sp-*` prefix) |
| `BAIDU_CODING_BASE_URL` | No | Override default base URL |

## Supported Models

All 7 models from the [official Coding Plan](https://cloud.baidu.com/doc/qianfan/s/imlg0beiu):

| Model | Context | Max Output |
|-------|---------|------------|
| `glm-5.1` | 198k | 131,072 |
| `glm-5` | 198k | 131,072 |
| `deepseek-v3.2` | 128k | 32,768 |
| `deepseek-v4-flash` | 1M | 131,072 |
| `kimi-k2.5` | 256k | 65,536 |
| `minimax-m2.5` | 192k | 131,072 |
| `ernie-4.5-turbo` | 128k | 12,288 |

## Aliases

`baidu`, `qianfan`, `baidu-coding-plan`, `baidu-qianfan` all resolve to `baidu-coding`.

## Notes

- Coding Plan keys (`sk-sp-*`) only work with the `/v2/coding/*` endpoints — they cannot access the standard Qianfan API
- Models not on the Coding Plan (e.g., `glm-4.7`) will return `403 coding_plan_model_not_supported`
- Context lengths are provider-specific and may differ from the model creator's native limits (e.g., GLM-5.1 is 198k on Baidu vs 204,800 on Z.AI)
