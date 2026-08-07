using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class DocumentOcrTextDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public DocumentStatus Status { get; set; }
        public string RawText { get; set; } = string.Empty;
        public string NormalizedText { get; set; } = string.Empty;
        public string? Provider { get; set; }
        public string? Language { get; set; }
        public int? Pages { get; set; }
        public DateTime? ExtractedAt { get; set; }
    }
}
