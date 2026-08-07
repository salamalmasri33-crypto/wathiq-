namespace eArchiveSystem.Application.DTOs
{
    public class DepartmentDto
    {
        public string Id { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string InstitutionId { get; set; } = string.Empty;
        public string? ParentDepartmentId { get; set; }
        public string? ParentDepartmentName { get; set; }
    }
}
