# Phase 1 Model Comparison

Status: awaiting manual Colab run and human review.

## Fixed candidates

| Candidate | Revision | License | Colab result |
| --- | --- | --- | --- |
| `Qwen/Qwen3-4B-Instruct-2507` | `cdbee75f17c01a7cc42f958dc650907174af0554` | Apache-2.0 | Pending |
| `microsoft/Phi-4-mini-instruct` | `cfbefacb99257ffa30c83adab238a50856ac3083` | MIT | Pending |

## Hard gates

- Valid structured-output rate: at least 90%.
- Unsupported claim references: zero.
- Minimal QLoRA smoke: 4-bit load, LoRA attachment, one optimizer step, safe
  adapter save, and reload all succeed.
- Exact model revision, environment, prompt, seed, and generation settings are
  recorded.

## Metrics to complete

| Metric | Qwen3 4B | Phi-4 Mini |
| --- | ---: | ---: |
| Valid output rate | Pending | Pending |
| Unsupported claim count | Pending | Pending |
| QLoRA smoke | Pending | Pending |
| Median generation latency | Pending | Pending |
| Peak GPU memory | Pending | Pending |
| Human rubric average | Pending | Pending |

## Decision

Selected model: pending.

Selection reason: pending manual benchmark and review.

Known failures and limitations: pending.
