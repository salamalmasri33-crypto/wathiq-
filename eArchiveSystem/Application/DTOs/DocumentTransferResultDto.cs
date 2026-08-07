using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class DocumentTransferResultDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public DocumentStatus Status { get; set; }
        public string? PreviousDepartmentId { get; set; }
        public string? PreviousDepartmentName { get; set; }
        public string TargetDepartmentId { get; set; } = string.Empty;
        public string TargetDepartmentName { get; set; } = string.Empty;
        public string Justification { get; set; } = string.Empty;
        public DateTime TransferredAt { get; set; }
    }
}
