# Rejected Experiments

The following experiments are research evidence only.

They must not be used as production pipelines.

## NoPnx-NP rejected systems

- AraBERTv2 alternative backbone.
- MARBERTv2 alternative backbone.
- AraELECTRA checkpoint averaging.
- Raw multi-seed ensemble.
- Calibrated multi-seed ensemble.
- Selective consensus gating. 
- Boundary-pair classifier.
- Stage-11-initialized dual-head model.

## Important Decision

Stage 11 AraELECTRA remains the adopted NoPnx-NP system.

Stage 16 and Stage 17 were rejected because their held-out improvements
were absent, too small, or unstable across folds.

## General Rule

A later experiment number does not mean that it is a better model.

Use only the systems listed in:

`docs/araseg/02_FINAL_VALIDATED_PIPELINES.md`