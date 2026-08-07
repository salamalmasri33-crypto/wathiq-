using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class DocumentTimelineDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public DocumentStatus Status { get; set; }
        public string OwnerUserId { get; set; } = string.Empty;
        public string? OwnerName { get; set; }
        public string? InstitutionId { get; set; }
        public string? DepartmentId { get; set; }
        public string? Department { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        public DateTime? SubmittedAt { get; set; }
        public DateTime? ReviewStartedAt { get; set; }
        public DateTime? ReviewedAt { get; set; }
        public DateTime? PublishedAt { get; set; }
        public DateTime? ArchivedAt { get; set; }
        public string? ReviewedByUserId { get; set; }
        public string? ReviewedByName { get; set; }
        public string? PublishedByUserId { get; set; }
        public string? PublishedByName { get; set; }
        public string? ArchivedByUserId { get; set; }
        public string? ArchivedByName { get; set; }
        public string? RejectionReason { get; set; }
        public List<DocumentTimelineEventDto> Events { get; set; } = new();
    }
}
