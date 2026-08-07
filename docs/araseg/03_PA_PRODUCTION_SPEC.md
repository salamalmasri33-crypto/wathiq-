# PA Production Inference Specification

## Status

This document is the source of truth for the first Wathiq AraSeg integration.

Do not modify these values during integration.

## Validated Configuration

- Track: PA.
- Maximum sequence length: 512.
- Stride: 64.
- Default probability threshold: 0.567.
- End-punctuation threshold: 0.32.
- Paragraph boundary rule: enabled.
- Force final document token as a boundary: enabled.
- Blind F1: 0.934.
- Submission ID: 861529.

## Recovered Historical Target

Recovered exact final PA ensemble target:

- Source account: A1.
- Notebook: `/content/drive/MyDrive/Colab Notebooks/Untitled1.ipynb`.
- Cell index: 81.
- Cell title: `PA BLIND — CURRENT + MICRO ENSEMBLE SUBMISSION`.
- Generated submission: `pa_current_micro_ens_a095_m005_d0543_e0310.zip`.
- Board submission: 861752.

Recovered exact model-input token mapping before PA ensemble tokenization:

- `"\n"` -> `"[PAR]"`.
- `"\\n"` -> `"[PAR]"`.
- `"[PAR]"` remains `"[PAR]"`.

Original tokens remain unchanged for:

- output;
- probability records;
- post-processing.

Recovered exact threshold comparison for future Milestone 5B:

- `probability >= threshold`

Recovered exact paragraph markers for future Milestone 5B:

- `["\\n", "\n", "[PAR]"]`

Recovered exact post-processing precedence for future Milestone 5B:

1. Apply the default threshold.
2. Apply the punctuation threshold.
3. Force paragraph-marker prediction to `0`.
4. Force the token immediately before a paragraph marker to `1`.
5. Force the final token to `1`.

Recovered frozen thresholds for future Milestone 5B:

- Default threshold: 0.543.
- Punctuation threshold: 0.310.
- Punctuation set: `[".", "؟", "?", "!", "…"]`.

## Required Processing Flow

1. Receive normalized OCR text.
2. Normalize line endings only.
3. Preserve punctuation.
4. Preserve paragraph boundaries.
5. Build original tokens and paragraph metadata.
6. Tokenize using the production tokenizer.
7. Split the input into overlapping chunks.
8. Run token-classification inference.
9. Map subtoken probabilities back to original tokens.
10. Average probabilities when tokens appear in overlapping chunks.
11. Apply the default threshold.
12. Apply the lower threshold to end-punctuation tokens.
13. Apply paragraph-boundary rules.
14. Force the final token to boundary label 1.
15. Reconstruct complete sentences.
16. Validate that every source token is preserved.

For the recovered PA ensemble target, keep two token representations:

1. Original tokens remain unchanged for results and later post-processing.
2. Model-input tokens map `"\n"` and `"\\n"` to `"[PAR]"` while preserving one token per original token.

## Input Source

The Wathiq backend should send:

1. `NormalizedOcrText`;
2. otherwise `RawOcrText`.

Do not use preprocessed search content after punctuation or stop-word removal.

## Prohibited Changes

Do not:

- replace the tokenizer;
- change chunk length;
- change stride;
- recalibrate thresholds;
- remove paragraph handling;
- add force-last behavior to another track automatically;
- use a rule-only sentence splitter as the production implementation.

## Model Artifact

The exact model artifact must be supplied separately.

Known original archived source:

`PA_finetune_20260723_104427/best_model`

The local deployment location must be configurable.

Do not invent a path when the artifact is unavailable.
