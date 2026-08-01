# Phase 1 Model Comparison

Status: complete; Qwen3 4B Instruct selected as the Phase 1 base model.

## Fixed candidates

| Candidate | Revision | License | Colab result |
| --- | --- | --- | --- |
| `Qwen/Qwen3-4B-Instruct-2507` | `cdbee75f17c01a7cc42f958dc650907174af0554` | Apache-2.0 | Passed all hard gates |
| `microsoft/Phi-4-mini-instruct` | `cfbefacb99257ffa30c83adab238a50856ac3083` | MIT | Failed strict JSON gate |

## Hard gates

- Valid structured-output rate: at least 90%.
- Unsupported claim references: zero.
- Minimal QLoRA smoke: 4-bit load, LoRA attachment, one optimizer step, safe
  adapter save, and reload all succeed.
- Exact model revision, environment, prompt, seed, and generation settings are
  recorded.

## Recorded Colab metrics

| Metric | Qwen3 4B | Phi-4 Mini |
| --- | ---: | ---: |
| Valid output rate | 100% (18/18) | 0% (0/18) |
| Unsupported claim-ID count | 0 | 0 |
| QLoRA smoke | Passed | Passed |
| Median generation latency | 10,159 ms | 8,686 ms |
| Peak GPU memory | 2,706 MB | 2,952 MB |
| Human rubric average | 2.5/5 | Not scored; excluded by hard gate |

Environment: Google Colab Tesla T4 (14,912 MB), Python 3.12.13, PyTorch
2.11.0+cu128, CUDA 12.8, and Transformers 5.14.1. Deterministic generation
used seed 42, sampling disabled, and a 384-token output bound.

## Decision

Selected model: `Qwen/Qwen3-4B-Instruct-2507` at revision
`cdbee75f17c01a7cc42f958dc650907174af0554`.

Selection reason: Qwen produced contract-valid JSON for all 18 measured outputs,
referenced no unsupported claim IDs, and completed the QLoRA smoke test. Phi
completed QLoRA but wrapped all 18 generations in Markdown fences, so every
output failed the strict JSON gate.

Known failures and limitations:

- Qwen's 2.5/5 human score reflects weak CTAs, limited differentiation, and
  unsupported benefit language in some email bodies. It is approved as a
  fine-tuning base, not as a production-ready outreach model.
- The automatic claim gate verifies claim IDs; semantic claims in generated
  prose still require human review and stronger Phase 2 evaluation.
- Phi was slightly faster but is ineligible because structured-output
  correctness is a hard gate.
- The one-step QLoRA loss is a feasibility signal only, not evidence of model
  improvement.
- The successful rerun applied the 384-token bound and native model loading as
  explicit notebook overrides. This finalization promotes the same values into
  the benchmark manifest so future runs have one configuration source.

## Result-bundle validation

The selected base model produced request `req_214b488813914b41`. The local
validator accepted its exact revision and SHA-256 digest
`3bee99856c5005827d563899c23906e27b6468690a5638af908dca3e5f46e3ff`.
Generated email content and model artifacts remain outside Git.
