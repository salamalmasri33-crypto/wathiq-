using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class WorkflowActionResultDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public DocumentStatus Status { get; set; }
        public DateTime? SubmittedAt { get; set; }
        public DateTime? ReviewStartedAt { get; set; }
        public DateTime? ReviewedAt { get; set; }
        public DateTime? PublishedAt { get; set; }
        public DateTime? ArchivedAt { get; set; }
        public string? RejectionReason { get; set; } // Set when the document is rejected.
    }
}
