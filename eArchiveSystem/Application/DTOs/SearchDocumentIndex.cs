using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class SearchDocumentIndex
    {
        public string Id { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
        public List<string> SentenceTexts { get; set; } = new();
        public string? Description { get; set; }
        public string? Snippet { get; set; }
        public string InstitutionId { get; set; } = string.Empty;
        public string DepartmentId { get; set; } = string.Empty;
        public string Department { get; set; } = string.Empty;
        public string UserId { get; set; } = string.Empty;
        public bool IsSensitive { get; set; }
        public string? BroadGenre { get; set; }
        public string? SpecificGenre { get; set; }
        public string? DocumentType { get; set; }
        public string? IssuingEntity { get; set; }
        public string? ReferenceNumber { get; set; }
        public DocumentStatus Status { get; set; }
        public DocumentPriority Priority { get; set; }
        public List<string> Tags { get; set; } = new();
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
