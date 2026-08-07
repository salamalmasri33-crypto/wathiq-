using System;
using System.Collections.Generic;

namespace eArchiveSystem.Application.Segmentation.Models
{
    public sealed record SegmentationResult
    {
        public string DocumentId { get; init; } = string.Empty;
        public string Status { get; init; } = string.Empty;
        public string Provider { get; init; } = string.Empty;
        public string Track { get; init; } = string.Empty;
        public string PipelineId { get; init; } = string.Empty;
        public string NormalizedText { get; init; } = string.Empty;
        public IReadOnlyList<SegmentedSentence> Sentences { get; init; } = Array.Empty<SegmentedSentence>();
    }
}
