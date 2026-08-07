namespace eArchiveSystem.Application.DTOs
{
    public class CurrentPermissionScopeDto
    {
        public string UserId { get; set; } = string.Empty;
        public string Role { get; set; } = string.Empty;
        public string? InstitutionId { get; set; }
        public string? DepartmentId { get; set; }
        public string? Department { get; set; }
        public SearchAccessScope SearchScope { get; set; } = new();
        public bool CanCreateForSelf { get; set; }
        public bool CanCreateForSameDepartmentMember { get; set; }
        public bool CanCreateForOtherDepartmentMember { get; set; }
        public bool CanCreateForOtherInstitutionMember { get; set; }
    }
}
