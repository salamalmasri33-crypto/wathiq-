# Lossless Raw-Text Token-Span Provider Contract

## Purpose

This document records the Wathiq production contract for converting natural
OCR text into exact ordered token spans before PA sentence-boundary inference.

It does not claim recovery of the original AraSeg shared-task tokenizer for
arbitrary OCR text.

## Benchmark Evidence Boundary

A separate Colab audit inspected:

- 758 PA documents;
- 531,091 tokens.

Observed results:

- 758/758 forward token-to-text alignments succeeded.
- 758/758 backward alignments succeeded.
- 758/758 alignments were unique.
- 758/758 documents reconstructed their text exactly.
- 0 failures occurred.
- 0 ambiguous documents occurred.
- Every audited document satisfied:

```text
text == " ".join(tokens)
```

The audited PA benchmark therefore behaved like a serialization of an already
prepared word-level token sequence.

This evidence is useful, but limited:

- it supports a deterministic Wathiq production contract;
- it does not prove an authoritative tokenizer for arbitrary natural OCR text;
- it must not be described as the recovered shared-task tokenizer for all
  future OCR content.

## Known Benchmark Anomaly

One known benchmark anomaly was observed:

- `226.` appeared as one mixed token.

This anomaly is documented for transparency only.

It is not encoded as a production rule.

The Wathiq production provider continues to emit punctuation as separate
source-preserving tokens.

## Production Tokenization Contract

The production raw-text token-span provider inside
`wathiq-araseg-service` performs a deterministic single-pass scan over one
authoritative source string.

Scanner precedence is fixed:

1. Literal `[PAR]` is emitted as one atomic token.
2. Literal `\n`, consisting of the two source characters backslash and `n`,
   is emitted as one atomic token.
3. Actual LF is emitted as one atomic token.
4. Any carriage return, including CRLF, is rejected without normalization.
5. Other Unicode whitespace is preserved as source gap content and is not
   emitted as a token.
6. Every Unicode punctuation character whose category begins with `P` is
   emitted as one separate token.
7. Every maximal remaining non-whitespace, non-punctuation sequence is emitted
   as one normal token.

The production provider does not:

- trim the source;
- normalize Unicode;
- collapse whitespace;
- replace line endings;
- search for tokens after token creation;
- infer or repair offsets;
- claim shared-task tokenizer recovery for arbitrary OCR text.

## Exact Source-Preservation Guarantees

For every emitted token:

```text
source[token.start_offset:token.end_offset] == token.text
```

The provider also guarantees:

- zero-based sequential token indexes;
- ordered, non-overlapping spans;
- deterministic output for the same source text;
- immutable returned token collections;
- no silent loss of non-whitespace source characters;
- exact recoverability of gaps through the original source text and offsets.

The original source string remains authoritative.

The provider must not reconstruct document display text by joining token
strings.

## LF-Only Requirement

The production raw-text provider accepts LF-only line endings.

Actual LF is preserved as a real source token because the PA pipeline already
has committed paragraph-marker handling for:

- actual `\n`;
- literal `\n`;
- literal `[PAR]`.

CR and CRLF are rejected fail-closed so that token offsets cannot be created
against a source representation that would later need normalization.

## Responsibility Boundary

Future Wathiq integration responsibility is:

- .NET will eventually send `NormalizedOcrText`;
- raw-text orchestration belongs to `wathiq-araseg-service`;
- raw-text tokenization belongs to `wathiq-araseg-service`;
- .NET must not reproduce model-specific tokenization;
- Hugging Face tokenization remains the model-subtoken stage inside the PA
  inference pipeline;
- the existing internal tokenized endpoint remains unchanged;
- a public or integration raw-text endpoint is a later milestone.

This keeps the Python service responsible for the exact raw-text-to-token-span
contract while preserving the existing PA model-input mapping behavior.

## Composition Boundary

Milestone 7D.2 adds only service-local composition:

```text
.NET / future client
-> NormalizedOcrText
-> RawTextSegmentationService
-> RawTextTokenSpanProvider
-> AbstractSegmentationPipeline / PAPipeline
-> SegmentationResult
```

This milestone does not add:

- a raw-text API endpoint;
- model-loading changes;
- automatic track routing;
- end-to-end OCR integration.

The existing internal tokenized endpoint remains unchanged, and a future
raw-text endpoint can delegate to the same orchestration component once the
API milestone is approved.

PA remains the only real production pipeline currently composed through this
raw-text service path.

## Internal Raw-Text Endpoint

Milestone 7D.3 adds one thin internal route:

```text
POST /internal/api/v1/segment-text
```

The route is:

- disabled by default;
- limited to `track = "PA"`;
- composed through `RawTextSegmentationService`;
- backed by one startup-retained `PAPipeline`;
- backed by one startup-constructed `LosslessUnicodeTokenSpanProvider`
  through one startup-retained `RawTextSegmentationService`.

Request fields are:

- `documentId`
- `text`
- `track`

Response fields remain aligned with the existing internal tokenized contract:

- `documentId`
- `status`
- `provider`
- `track`
- `pipelineId`
- `normalizedText`
- `segments`

Each segment retains:

- `index`
- `text`
- `startToken`
- `endToken`

Operational constraints remain:

- no authentication is implemented yet;
- deployment must remain internal or otherwise network-restricted;
- LF input is supported;
- CR and CRLF fail closed through the existing controlled error path;
- the existing internal tokenized endpoint remains available;
- the public `/api/v1/segment` endpoint remains the fake contract endpoint;
- model loading still occurs once at startup when internal PA endpoints are enabled.
