# Final Validated AraSeg Pipelines

These are the final adopted systems.

Rejected later experiments must not replace them.

## PA

Final adopted pipeline:

- Fine-tuned PA model.
- Source initialization: final NoPnx-PA model.
- Maximum length: 512.
- Stride: 64.
- Default threshold: 0.567.
- End-punctuation threshold: 0.32.
- Paragraph-boundary rule: enabled.
- Force-last rule: enabled.

Blind result:

- Precision: 93.4%.
- Recall: 93.9%.
- F1: 93.4%.
- Submission ID: 861529.

This is the first production pipeline to integrate with Wathiq.

## NoPnx-PA

Final adopted pipeline:

- Two exact `[PAR]` models.
- Seeds: 2026 and 13.
- Ensemble weights: 0.40 and 0.60.
- Threshold: 0.45.
- `[PAR]` label forced to 0.
- Token immediately before `[PAR]` forced to 1.

Blind result:

- Precision: 87.4%.
- Recall: 89.3%.
- F1: 87.9%.
- Submission ID: 859217.

## NP

Final adopted pipeline:

- Base NP model.
- AraSeg token classification with maximum length 128 and stride 16.
- Stage 5C multi-seed ensemble.
- Seed/model weights: 0.40, 0.30, 0.30.
- Final threshold: 0.415.

Blind result:

- Precision: 92.5%.
- Recall: 88.5%.
- F1: 90.0%.
- Submission ID: 865951.

## NoPnx-NP

Final adopted pipeline:

- Stage 11 AraELECTRA.
- Backbone: `aubmindlab/araelectra-base-discriminator`.
- Official NoPnx-NP Train split only.
- Maximum length: 256.
- Stride: 32.
- Accepted Stage 11 blend and threshold configuration.

Blind result:

- Precision: 83.9%.
- Recall: 87.0%.
- F1: 84.8%.
- Submission ID: 867449.

## Production Decision

Initial Wathiq integration:

- Implement PA only.
- Do not implement an automatic router yet.
- Do not load all four models.
- Keep the common abstraction extensible for future tracks.