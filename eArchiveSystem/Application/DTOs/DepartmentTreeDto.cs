namespace eArchiveSystem.Application.DTOs
{
    public class DepartmentTreeDto
    {
        public string Id { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string InstitutionId { get; set; } = string.Empty;
        public string? ParentDepartmentId { get; set; }
        public List<DepartmentTreeDto> Children { get; set; } = new();
    }
}
