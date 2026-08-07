namespace eArchiveSystem.Application.DTOs
{
    public class AddDepartmentDto
    {
        public string Name { get; set; } = string.Empty;
        public string? InstitutionId { get; set; }
        public string? ParentDepartmentId { get; set; }
    }
}
