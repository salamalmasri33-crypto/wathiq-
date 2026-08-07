using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class DocumentSegmentationDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public SegmentationStatus Status { get; set; }
        public string? Provider { get; set; }
        public string Track { get; set; } = string.Empty;
        public string? PipelineId { get; set; }
        public string? NormalizedText { get; set; }
        public List<DocumentSentenceDto> Sentences { get; set; } = new();
        public string? ErrorCode { get; set; }
        public string? ErrorMessage { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        public DateTime? CompletedAt { get; set; }
    }
}
