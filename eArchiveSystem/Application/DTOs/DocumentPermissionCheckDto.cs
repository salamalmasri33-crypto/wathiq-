using eArchiveSystem.Domain.Models;

namespace eArchiveSystem.Application.DTOs
{
    public class DocumentPermissionCheckDto
    {
        public string DocumentId { get; set; } = string.Empty;
        public string OwnerUserId { get; set; } = string.Empty;
        public string? InstitutionId { get; set; }
        public string? DepartmentId { get; set; }
        public string? Department { get; set; }
        public DocumentStatus Status { get; set; }
        public bool CanView { get; set; }
        public bool CanEdit { get; set; }
        public bool CanDelete { get; set; }
        public bool CanSubmit { get; set; }
        public bool CanStartReview { get; set; }
        public bool CanApprove { get; set; }
        public bool CanReject { get; set; }
        public bool CanPublish { get; set; }
        public bool CanArchive { get; set; }
    }
}
