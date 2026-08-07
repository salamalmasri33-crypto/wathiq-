# AraSeg 2026 Shared Task Context

## Problem

OCR converts scanned Arabic documents into text, but it does not reliably
identify sentence boundaries.

OCR output may contain:

- missing punctuation;
- incorrect punctuation;
- merged lines;
- lost paragraph boundaries;
- long unstructured text blocks.

AraSeg detects whether each original token represents the end of a sentence.

The output is a binary boundary label per token:

- `0`: the sentence continues;
- `1`: the sentence ends after this token.

## Relationship to Wathiq

Wathiq currently performs:

Document
→ OCR
→ Raw OCR text
→ Normalized OCR text
→ Search and document analysis

AraSeg adds sentence-level structure:

Document
→ OCR
→ Normalized OCR text
→ AraSeg
→ Structured sentences
→ Search, metadata, summaries, and display

OCR tells Wathiq what text exists in the document.
AraSeg tells Wathiq how that text is structured.

## Tracks

The shared task contains four text conditions:

### PA

Punctuation and paragraph information are available.

Representative Wathiq scenario:
high-quality OCR output with preserved punctuation and paragraphs.

### NoPnx-PA

Punctuation is removed, but paragraph information is available.

Representative scenario:
OCR preserves lines or paragraphs but misses punctuation.

### NP

Punctuation is available, but paragraph information is not available.

Representative scenario:
OCR preserves punctuation but merges paragraph structure.

### NoPnx-NP

Neither punctuation nor paragraph information is available.

Representative scenario:
noisy OCR output with weak structural information.

## Dataset Rule

The tracks use the same underlying documents with different preprocessing.

Cross-track copies do not provide new documents and may create duplicates.

Any pretrained model backbone is allowed, but task fine-tuning data must
come only from official AraSeg Train splits.

Dev may be used only for development and model selection.

Blind/Test must never be used for training or adaptation.

## Integration Scope

Phase 1 integrates only the final PA pipeline.

The other validated pipelines are documented for future routing support,
but they must not be implemented during the initial milestone.