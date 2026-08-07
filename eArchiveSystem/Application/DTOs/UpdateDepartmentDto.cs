namespace eArchiveSystem.Application.DTOs
{
    public class UpdateDepartmentDto
    {
        public string Name { get; set; } = string.Empty;
        public string? ParentDepartmentId { get; set; }
    }
}
